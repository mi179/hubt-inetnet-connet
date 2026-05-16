"""
校园网 ePortal 自动登录模块。

实现基于 requests 会话的认证流程，支持：
  - Cookie 管理（自动跟踪 JSESSIONID）
  - 请求级别重试（指数退避）
  - 会话级别重试（整体重建）
  - 响应错误捕获与日志

用法见底部 __main__ 示例，或在 cli.py 中通过 login 子命令调用。
"""

import time
import logging
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


# ── 数据结构 ──────────────────────────────────────────────

@dataclass
class PortalCredentials:
    """ePortal 认证凭据。"""

    user_id: str                                   # 学号
    password: str                                  # 客户端加密后的密码 hash
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


# ── Session 工厂 ──

def create_session(retries: int = DEFAULT_MAX_RETRIES,
                   backoff: float = 0.5) -> requests.Session:
    """创建带连接级重试的 requests Session。"""
    session = requests.Session()

    # 连接级自动重试（应对临时网络闪断）
    retry_strategy = Retry(
        total=retries,
        backoff_factor=backoff,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["POST"],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    # 通用请求头
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
                   password: str = "",
                   server: str = "LT",
                   server_name: str = "联通",
                   user_group: str = "工程技术学院学生") -> None:
    """注入 ePortal 前端记住的 Cookie（可选，部分 portal 需要）。"""
    jar = {
        "EPORTAL_COOKIE_OPERATORPWD": "",
        "EPORTAL_COOKIE_DOMAIN": "true",
        "EPORTAL_COOKIE_SAVEPASSWORD": "true",
        "EPORTAL_COOKIE_NEWV": "true",
        "EPORTAL_AUTO_LAND": "",
        "EPORTAL_COOKIE_SERVER": server,
        "EPORTAL_COOKIE_SERVER_NAME": server_name,
        "EPORTAL_USER_GROUP": user_group,
    }
    if username:
        jar["EPORTAL_COOKIE_USERNAME"] = username
    if password:
        jar["EPORTAL_COOKIE_PASSWORD"] = password

    # requests 的 cookie jar 需要 domain
    for name, value in jar.items():
        session.cookies.set(name, value, domain=host, path="/")


# ── 核心登录逻辑 ──

def build_form_data(creds: PortalCredentials) -> dict[str, str]:
    """构造 x-www-form-urlencoded 请求体。"""
    return {
        "userId": creds.user_id,
        "password": creds.password,
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
               timeout: int) -> LoginResult:
    """
    无重试的底层的登录调用。
    
    Returns:
        LoginResult — 无论网络/HTTP 异常都不会抛给上层。
    """
    url = f"http://{host}/eportal/InterFace.do?method=login"
    data = build_form_data(creds)

    try:
        resp = session.post(url, data=data, timeout=timeout)
        body = resp.text

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
    执行一次 ePortal 登录（带请求级重试，同一 Session）。
    
    参数:
        creds:      认证凭据
        host:       认证服务器地址（IP 或域名）
        referer:    Referer URL，为空时自动根据 queryString 构建
        session:    可复用的 Session（自动共享 Cookie）；None 则新建
        max_retries: 网络失败后的重试次数（指数退避）
        timeout:    单次请求超时秒数

    返回:
        LoginResult — 包含成功/失败、状态码、响应体、错误信息。
    """
    own_session = False
    if session is None:
        session = create_session(max_retries)
        # 注入原始 cURL 中的那些 Cookie（可选）
        inject_cookies(session, host,
                       username=creds.user_id,
                       password=creds.password)
        own_session = True

    # 补齐 Origin / Referer
    if not referer:
        referer = build_referer(host, creds)
    prepare_session(session, host, referer)

    last_result = LoginResult(success=False, error="未执行")

    for attempt in range(1, max_retries + 1):
        logger.debug("🔄 登录尝试 %d/%d  %s:%s",
                     attempt, max_retries, host, creds.user_id)

        result = _raw_login(session, host, creds, timeout)

        if result.success:
            return result

        last_result = result

        if attempt < max_retries:
            wait = 2 ** attempt   # 指数退避: 2 → 4 → 8 秒
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
    外层重试 —— 每次挂掉都重建整个 Session（清空 Cookie、重置连接池）。
    
    适合在持久性失败后（如认证服务器重启、Session 过期）从头再来。
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
            delay = 5 * attempt   # 5 → 10 → 15 秒
            logger.info("⏳ 休息 %d 秒后重建 Session...", delay)
            time.sleep(delay)

    return result


# ── 辅助函数 ──

def build_referer(host: str, creds: PortalCredentials) -> str:
    """从 queryString 等信息构造 Referer URL。

    若 creds.query_string 非空，优先填入其中提取的 wlanuserip 等参数；
    否则使用示例中的默认值。
    """
    # 简单从 queryString 中提取参数（如已编码则无需解码）
    params = {
        "wlanuserip": "10.9.213.248",
        "wlanacname": "logic",
        "nasip": "10.253.0.17",
        "wlanparameter": "50-bb-b5-db-26-36",
        "userlocation": "ethtrunk/3:3960.0",
    }

    # 如果 queryString 包含这些参数，尝试提取出来覆盖默认值
    if creds.query_string:
        for key in params:
            marker = f"{key}%3D"  # URL 编码的 =
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


def parse_login_response(body: str) -> dict:
    """解析认证服务器返回的消息。

    有些 portal 返回纯 JSON，有些返回 HTML 片段。
    这里统一尝试 JSON 解析，失败则返回 {'raw': body}。
    """
    if not body:
        return {}
    try:
        return __import__("json").loads(body)
    except (ValueError, TypeError):
        return {"raw": body[:500]}


# ── 独立运行入口 ──
#   python -m cyber_lobster.network_login

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s %(message)s",
    )

    creds = PortalCredentials(
        user_id="20240000000",
        # 密码 hash 太长，建议存入配置文件或环境变量
        password="abcd1234...<从配置文件或环境变量读取>",
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
        print("🎉 登录成功！（可能需要访问 http://www.baidu.com 确认）")
        print("响应:", result.body[:200])
    else:
        print(f"❌ 登录失败: {result.error}")
        print(f"HTTP {result.status_code}: {result.body[:200]}")
