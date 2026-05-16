"""
校园网 ePortal 自动登录模块。

实现基于 requests 会话的完整认证流程：
  - 自动获取 RSA 公钥（pageInfo API）
  - 客户端加密密码（反转 → RSA-1024，与浏览器 JS 一致）
  - Cookie 管理（自动跟踪 JSESSIONID）
  - 请求级 / 会话级重试 + 指数退避

直接从 `cyber-lobster login --from-config` 调用。
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger("cyber-lobster.login")

# ── 可调常量 ──────────────────────────────────────────────

DEFAULT_HOST = "172.16.54.18"                     # 认证服务器
DEFAULT_SERVICE = "DX"                            # 运营商: DX / LT / YD
DEFAULT_TIMEOUT = 10                              # 单次请求超时（秒）
DEFAULT_MAX_RETRIES = 3                           # 请求级重试次数
DEFAULT_SESSION_RETRIES = 3                       # 会话级重试次数

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/148.0.0.0 Safari/537.36 Edg/148.0.0.0"
)

# 已加密的密码 hash 是 256 位 hex（1024-bit RSA 输出）
RE_ENCRYPTED_HASH = re.compile(r"^[0-9a-f]{256}$")


# ── 数据结构 ──────────────────────────────────────────────

@dataclass
class PortalCredentials:
    """ePortal 认证凭据。

    注意:
        password 可以填原始密码（明文），登录时会自动 RSA 加密；
        也可以填已加密的 256 位 hex hash（跳过加密步骤）。
    """

    user_id: str                                   # 学号
    password: str                                  # 明文密码 或 已加密 hash
    service: str = DEFAULT_SERVICE                 # 运营商
    query_string: str = ""                         # 原请求中的 queryString
    operator_pwd: str = ""
    operator_user_id: str = ""
    validcode: str = ""
    password_encrypt: bool = True


@dataclass
class LoginResult:
    """登录结果。"""
    success: bool
    status_code: Optional[int] = None
    body: str = ""
    error: str = ""


# ── RSA 加密（与浏览器 JS 行为一致） ──

def fetch_public_key(
    host: str,
    query_string: str,
    session: Optional[requests.Session] = None,
    timeout: int = 10,
) -> dict:
    """调用 pageInfo 接口获取 RSA 公钥。

    返回:
        {"publicKeyExponent": "10001",
         "publicKeyModulus": "<256-hex-char>"}
    失败时返回空 dict。
    """
    url = f"http://{host}/eportal/InterFace.do?method=pageInfo"
    data = {"queryString": query_string}

    own_session = False
    if session is None:
        session = requests.Session()
        own_session = True

    try:
        resp = session.post(url, data=data, timeout=timeout)
        if resp.status_code == 200 and resp.text:
            info = resp.json()
            exp = info.get("publicKeyExponent", "")
            mod = info.get("publicKeyModulus", "")
            if exp and mod:
                logger.info("✅ 获取 RSA 公钥成功")
                return {"publicKeyExponent": exp, "publicKeyModulus": mod}
    except Exception as exc:
        logger.warning("获取公钥失败: %s", exc)

    return {}


def rsa_encrypt_password(password: str, modulus_hex: str, exponent_hex: str = "10001") -> str:
    """模拟浏览器 JS 的 RSA 加密流程。

    步骤:
      1. 密码反转:  password -> password[::-1]
      2. 取 charCode 得到字节数组
      3. 补零至 chunkSize (2 * (位数 - 1))
      4. 按小端序组装为大整数
      5. m^e mod n
      6. 输出 hex 字符串

    参数:
        password:     原始密码（明文）
        modulus_hex:  公钥 modulus（hex）
        exponent_hex: 公钥 exponent（hex，通常 10001）

    返回:
        密文 hex 字符串（不含空格），约 256 字符。
    """
    # 1. 反转
    rev = password[::-1]  # 与 JS: password.split("").reverse().join("") 一致

    # 2. charCode → 字节数组（JS charCodeAt 对 ASCII 返回 [0,127]）
    raw_bytes = rev.encode("utf-8", errors="replace")

    # 3. 计算 chunkSize（与 JS RSAKeyPair 构造函数一致）
    #    JS: biFromHex → BigInt  digits[] 是 16-bit 小端序
    #    modulus 有 N 个 digit → biHighIndex = N-1
    #    chunkSize = 2 * biHighIndex
    mod_digits = (len(modulus_hex) + 3) // 4  # 每 4 hex chars = 1 digit
    bi_high_index = mod_digits - 1
    # 但 biHighIndex 返回的是最高非零 digit 索引，
    # 对于满 1024-bit key，就是 N-1。
    # 安全起见也检查一下实际最高非零值的位置
    for i in range(bi_high_index, -1, -1):
        start = max(0, len(modulus_hex) - (i + 1) * 4)
        chunk = modulus_hex[start: start + 4]
        if int(chunk, 16) != 0:
            bi_high_index = i
            break

    chunk_size = 2 * bi_high_index

    # 补零至 chunk_size 字节
    if len(raw_bytes) > chunk_size:
        logger.warning("密码过长（%d > %d），将被截断", len(raw_bytes), chunk_size)
        raw_bytes = raw_bytes[:chunk_size]
    padded = raw_bytes + b"\x00" * (chunk_size - len(raw_bytes))

    # 4. 小端序 → 大整数（匹配 JS digit 排列）
    m = int.from_bytes(padded, "little")

    # 5. RSA 加密
    e = int(exponent_hex, 16)
    n = int(modulus_hex, 16)
    c = pow(m, e, n)

    # 6. hex 输出（小写，无 0x 前缀）
    cipher_hex = format(c, "x")

    # 补充前导零到 256 字符（JS biToHex 的行为）
    expected_len = len(modulus_hex)
    if len(cipher_hex) < expected_len:
        cipher_hex = cipher_hex.zfill(expected_len)

    return cipher_hex


def ensure_encrypted_password(
    creds: PortalCredentials,
    host: str,
    query_string: str = "",
    session: Optional[requests.Session] = None,
) -> str:
    """确保 password 是已加密的 hash。

    - 如果 `creds.password` 已经是 256 位 hex → 直接返回
    - 否则 → 获取公钥 → RSA 加密 → 返回 hex
    """
    pwd = creds.password.strip()
    if RE_ENCRYPTED_HASH.match(pwd):
        logger.info("密码已是加密 hash，跳过 RSA")
        return pwd

    qs = query_string or creds.query_string
    if not qs:
        logger.info("🔍 queryString 为空，自动检测中...")
        qs = detect_query_string()
    if not qs:
        logger.warning("⚠ 自动检测失败，回退默认值")
        qs = (
            "wlanuserip%3D10.9.213.248"
            "%26wlanacname%3Dlogic"
            "%26nasip%3D10.253.0.17"
            "%26wlanparameter%3D50-bb-b5-db-26-36"
            "%26url%3Dhttp%3A%2F%2Fwww.baidu.com%2F"
            "%26userlocation%3Dethtrunk%2F3%3A3960.0"
        )

    key = fetch_public_key(host, qs, session=session)
    if not key:
        raise RuntimeError("无法获取 RSA 公钥，登录失败")

    logger.info("🔐 RSA 加密密码中...")
    encrypted = rsa_encrypt_password(pwd, key["publicKeyModulus"], key["publicKeyExponent"])
    logger.debug("加密结果: %s...", encrypted[:32])
    return encrypted


# ── Session 工厂 ──

def create_session(retries: int = DEFAULT_MAX_RETRIES,
                   backoff: float = 0.5) -> requests.Session:
    """创建带连接级重试的 requests Session。"""
    session = requests.Session()

    retry_strategy = Retry(
        total=retries,
        backoff_factor=backoff,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["POST"],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    session.headers.update({
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
        "User-Agent": USER_AGENT,
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    })

    return session


def prepare_session(session: requests.Session,
                    host: str,
                    referer: str = "") -> None:
    """为本次请求补齐 Host 相关的动态 header。"""
    session.headers["Origin"] = f"http://{host}"
    if referer:
        session.headers["Referer"] = referer


def inject_cookies(session: requests.Session,
                   host: str,
                   username: str = "",
                   password: str = "") -> None:
    """注入 ePortal 前端 Cookie（不含中文值，避免 latin-1 编码崩溃）。"""
    jar = {
        "EPORTAL_COOKIE_OPERATORPWD": "",
        "EPORTAL_COOKIE_DOMAIN": "true",
        "EPORTAL_COOKIE_SAVEPASSWORD": "true",
        "EPORTAL_COOKIE_NEWV": "true",
        "EPORTAL_AUTO_LAND": "",
        "EPORTAL_COOKIE_SERVER": "LT",
        "EPORTAL_COOKIE_SERVER_NAME": "%E8%81%94%E9%80%9A",
        "EPORTAL_USER_GROUP": "%E5%B7%A5%E7%A8%8B%E6%8A%80%E6%9C%AF%E5%AD%A6%E9%99%A2%E5%AD%A6%E7%94%9F",
    }
    if username:
        jar["EPORTAL_COOKIE_USERNAME"] = username
    if password:
        jar["EPORTAL_COOKIE_PASSWORD"] = password

    for name, value in jar.items():
        session.cookies.set(name, value, domain=host, path="/")


# ── 核心登录逻辑 ──

def build_form_data(creds: PortalCredentials,
                    encrypted_password: str) -> dict[str, str]:
    """构造 x-www-form-urlencoded 请求体。"""
    return {
        "userId": creds.user_id,
        "password": encrypted_password,
        "service": creds.service,
        "queryString": creds.query_string,
        "operatorPwd": creds.operator_pwd,
        "operatorUserId": creds.operator_user_id,
        "validcode": creds.validcode,
        "passwordEncrypt": "true" if creds.password_encrypt else "false",
    }


def _raw_login(session: requests.Session,
               host: str,
               creds: PortalCredentials,
               encrypted_password: str,
               timeout: int) -> LoginResult:
    """无重试的底层登录调用。"""
    url = f"http://{host}/eportal/InterFace.do?method=login"
    data = build_form_data(creds, encrypted_password)

    try:
        resp = session.post(url, data=data, timeout=timeout)
        body = resp.text

        # ePortal 返回 GBK 编码，requests.text 用 UTF-8 解码会乱码
        # 改用 resp.content 并尝试 GBK 优先
        raw = resp.content
        body = _decode_response(raw)
        if resp.status_code == 200:
            logger.info("✅ 登录 HTTP 200 —— %s", body[:120])
            return LoginResult(success=True, status_code=200, body=body)
        else:
            logger.warning("登录返回 HTTP %d: %s", resp.status_code, body[:200])
            return LoginResult(success=False, status_code=resp.status_code, body=body)

    except requests.exceptions.Timeout:
        msg = f"POST 超时（>{timeout}s）"
        logger.warning(msg)
        return LoginResult(success=False, error=msg)

    except requests.exceptions.ConnectionError as e:
        msg = f"连接失败: {e}"
        logger.warning(msg)
        return LoginResult(success=False, error=msg)

    except requests.exceptions.RequestException as e:
        msg = f"请求异常: {e}"
        logger.error(msg)
        return LoginResult(success=False, error=msg)


def login(creds: PortalCredentials,
          host: str = DEFAULT_HOST,
          referer: str = "",
          session: Optional[requests.Session] = None,
          max_retries: int = DEFAULT_MAX_RETRIES,
          timeout: int = DEFAULT_TIMEOUT) -> LoginResult:
    """
    执行一次 ePortal 登录。

    自动处理：
      - RSA 公钥获取（若密码为明文）
      - 密码加密（反转 + RSA-1024）
      - Cookie 注入
      - 指数退避重试

    参数:
        creds:       认证凭据（password 可为明文或已加密 hash）
        host:        认证服务器地址
        referer:     Referer URL，空则自动构建
        session:     可复用的 Session（自动共享 Cookie）
        max_retries: 网络失败后的重试次数
        timeout:     单次请求超时秒数

    返回:
        LoginResult
    """
    own_session = False
    if session is None:
        session = create_session(max_retries)
        inject_cookies(session, host,
                       username=creds.user_id,
                       password=creds.password)
        own_session = True

    # ── 自动检测 queryString（若为空）──
    if not creds.query_string:
        logger.info("🔍 queryString 为空，尝试自动检测...")
        detected = detect_query_string()
        if detected:
            creds.query_string = detected
            logger.info("✅ 自动检测到 queryString")
        else:
            logger.warning("⚠ 自动检测失败，仍使用默认值")

    if not referer:
        referer = build_referer(host, creds)
    prepare_session(session, host, referer)

    # ── RSA 加密密码（若尚未加密）──
    try:
        encrypted_pwd = ensure_encrypted_password(creds, host, session=session)
    except RuntimeError as exc:
        return LoginResult(success=False, error=str(exc))

    last_result = LoginResult(success=False, error="未执行")

    for attempt in range(1, max_retries + 1):
        logger.debug("🔄 登录尝试 %d/%d  %s:%s",
                     attempt, max_retries, host, creds.user_id)

        result = _raw_login(session, host, creds, encrypted_pwd, timeout)

        if result.success:
            return result

        last_result = result

        if attempt < max_retries:
            wait = 2 ** attempt
            logger.info("⏳ %d 秒后重试...", wait)
            time.sleep(wait)

    return last_result


def login_with_session_retry(
        creds: PortalCredentials,
        host: str = DEFAULT_HOST,
        max_session_attempts: int = DEFAULT_SESSION_RETRIES,
        request_retries: int = DEFAULT_MAX_RETRIES,
        timeout: int = DEFAULT_TIMEOUT,
) -> LoginResult:
    """
    外层重试 —— 每次挂掉都重建整个 Session。
    """
    for attempt in range(1, max_session_attempts + 1):
        logger.info("🔄 会话级重试 %d/%d", attempt, max_session_attempts)

        session = create_session(request_retries)
        inject_cookies(session, host,
                       username=creds.user_id,
                       password=creds.password)

        result = login(creds, host=host, session=session,
                       max_retries=request_retries, timeout=timeout)
        if result.success:
            return result

        if attempt < max_session_attempts:
            delay = 5 * attempt
            logger.info("⏳ 休息 %d 秒后重建 Session...", delay)
            time.sleep(delay)

    return result


# ── queryString 自动检测 ──

def detect_query_string(
    test_url: str = "http://www.baidu.com/",
    timeout: int = 5,
) -> str:
    """访问一个外网地址，从重定向中捕获 queryString。

    未认证时，网络会 302 跳到:
        http://<portal>/eportal/index.jsp?wlanuserip=...&...
    从中提取 query 部分返回（不包含前导 ?）。

    返回:
        queryString 字符串（如 "wlanuserip=10.9.213.248&..."），
        未捕获到时返回空字符串。
    """
    try:
        resp = requests.get(test_url, timeout=timeout, allow_redirects=False)
    except requests.RequestException:
        return ""

    # 检查 302 跳转到 portal
    location = resp.headers.get("Location", "")
    if not location:
        return ""

    # 提取 ? 后的参数
    if "?" in location:
        qs = location.split("?", 1)[1]
        logger.info("📡 自动捕获 queryString: %s...", qs[:80])
        return qs

    return ""


def build_double_encoded_qs(raw_query_string: str) -> str:
    """将 queryString URL 编码一次（适配 ePortal 的 POST 格式）。

    浏览器行为: JS 取 location.search.substr(1) 得到原始参数，
    然后 JavaScript 的 encodeURIComponent 对其编码。
    这里用 requests 的 URL 编码行为模拟（通过 data=dict 自动编码）。
    """
    # 直接返回原始参数，requests 的 data= 会帮我们编码一次
    return raw_query_string


# ── 辅助函数 ──

def build_referer(host: str, creds: PortalCredentials) -> str:
    """构造 Referer URL。"""
    params = {
        "wlanuserip": "10.9.213.248",
        "wlanacname": "logic",
        "nasip": "10.253.0.17",
        "wlanparameter": "50-bb-b5-db-26-36",
        "userlocation": "ethtrunk/3:3960.0",
    }

    if creds.query_string:
        for key in params:
            marker = f"{key}%3D"
            if marker in creds.query_string:
                try:
                    start = creds.query_string.index(marker) + len(marker)
                    end = creds.query_string.index("%26", start) if "%26" in creds.query_string[start:] else len(creds.query_string)
                    params[key] = creds.query_string[start:end]
                except ValueError:
                    pass

    return (
        f"http://{host}/eportal/index.jsp?"
        f"wlanuserip={params['wlanuserip']}"
        f"&wlanacname={params['wlanacname']}"
        f"&nasip={params['nasip']}"
        f"&wlanparameter={params['wlanparameter']}"
        f"&url=http://www.baidu.com/"
        f"&userlocation={params['userlocation']}"
    )


def _decode_response(raw: bytes) -> str:
    """尝试用 GBK 解码，失败回退 UTF-8（ePortal 返回 GBK 编码）。"""
    for charset in ("gbk", "utf-8", "latin-1"):
        try:
            return raw.decode(charset)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace")


def parse_login_response(body: str) -> dict:
    """解析 ePortal 返回的 JSON 响应。"""
    if not body:
        return {}
    try:
        return json.loads(body)
    except (ValueError, TypeError):
        return {"raw": body[:500]}


# ── 注销 ──

def logout(host: str = DEFAULT_HOST, timeout: int = 5) -> LoginResult:
    """发送 ePortal 注销请求。

    尝试多个常见注销端点:
      1. /eportal/InterFace.do?method=logout
      2. /drcom/logout
      3. /cgi-bin/srun_portal?action=logout
    """
    endpoints = [
        f"http://{host}/eportal/InterFace.do?method=logout",
        f"http://{host}/drcom/logout",
        f"http://{host}/cgi-bin/srun_portal",
    ]
    # 第三个需要带参数
    params_list = [
        {},
        {},
        {"action": "logout"},
    ]

    for url, params in zip(endpoints, params_list):
        try:
            resp = requests.post(url, data=params, timeout=timeout)
            if resp.status_code == 200:
                body = _decode_response(resp.content)
                logger.info("注销请求已发送 (%s)", url)
                return LoginResult(success=True, status_code=200, body=body)
        except requests.RequestException as exc:
            logger.debug("注销端点 %s 失败: %s", url, exc)
            continue

    return LoginResult(success=False, error="所有注销端点均失败")


# ── 独立运行入口 ──
#   python -m cyber_lobster.network_login

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s %(message)s",
    )

    creds = PortalCredentials(
        user_id="20240000000",
        password="ExamplePass123",   # 明文密码，会自动 RSA 加密
        service="DX",
        query_string=(
            "wlanuserip%3D10.9.213.248"
            "%26wlanacname%3Dlogic"
            "%26nasip%3D10.253.0.17"
            "%26wlanparameter%3D50-bb-b5-db-26-36"
            "%26url%3Dhttp%3A%2F%2Fwww.baidu.com%2F"
            "%26userlocation%3Dethtrunk%2F3%3A3960.0"
        ),
    )

    result = login_with_session_retry(creds)
    if result.success:
        print("🎉 登录成功！（可访问 http://www.baidu.com 确认）")
        resp_data = parse_login_response(result.body)
        if resp_data:
            print("服务器响应:", json.dumps(resp_data, ensure_ascii=False, indent=2)[:500])
    else:
        print(f"❌ 登录失败: {result.error}")
        print(f"HTTP {result.status_code}: {result.body[:300]}")
