"""日志开关。

默认不输出任何日志（热路径零开销）。想看每一步细节时::

    from dispatcher3 import enable_logging
    enable_logging()          # 打开 DEBUG 级别

注意：enable_logging() 只管 dispatcher3.* 这几个 logger。
你自己模块里 logging.getLogger(__name__) 的 debug 需要自己配置::

    import logging
    logging.basicConfig(level=logging.DEBUG)
"""
import logging
import sys

LOG_FORMAT = "%(asctime)s.%(msecs)03d %(levelname)-5s %(name)-22s │ %(message)s"
DATE_FORMAT = "%H:%M:%S"

_HANDLER_FLAG = "_dispatcher3_handler"


def _make_handler(stream):
    stream = stream or sys.stderr
    # Windows 控制台/重定向到 cp936 文件时，emoji 会触发 UnicodeEncodeError，
    # 这里把编码错误降级为替换字符，避免日志把业务打挂。
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is not None:
        try:
            reconfigure(errors="replace")
        except (ValueError, OSError):
            pass
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    setattr(handler, _HANDLER_FLAG, True)
    return handler


def enable_logging(level=logging.DEBUG, stream=None):
    """打开 dispatcher3 的详细日志。

    行为分两种情况：

    * 如果 root logger 已经有 handler（说明调用方自己配置过 logging，
      例如 basicConfig / dictConfig / pytest），本函数**不装自己的 handler**，
      只把 dispatcher3 的级别调开，让日志走调用方的 handler。
      这样不会和调用方的配置打架，也不会重复输出。
    * 如果 root logger 没有任何 handler，本函数给 dispatcher3 装一个
      带 emoji 格式的 StreamHandler。

    注意：本函数只影响 dispatcher3.* 这些 logger，不会去动 root，
    也不会让调用方自己模块的 logger.debug 生效。

    Args:
        level: 日志级别，默认 DEBUG（能看到每一步）。传 INFO 就看不到
            DEBUG 级别的逐次分发细节。
        stream: 输出流，仅在需要自建 handler 时生效，默认 sys.stderr。

    Returns:
        dispatcher3 的 logger。
    """
    logger = logging.getLogger("dispatcher3")
    logger.setLevel(level)

    root = logging.getLogger()
    if root.handlers:
        # 调用方已经配置过 logging，交给他们的 handler
        logger.propagate = True
        return logger

    logger.propagate = False
    if not any(getattr(h, _HANDLER_FLAG, False) for h in logger.handlers):
        logger.addHandler(_make_handler(stream))
    return logger


def disable_logging():
    """关闭并移除 dispatcher3 的日志 handler，恢复静默。

    级别复位为 NOTSET（继承 root），而不是写死 WARNING —— 否则调用方之后
    再调 basicConfig(level=DEBUG) 也不会生效，因为 dispatcher3 自己的
    WARNING 级别会把 DEBUG 记录挡在门外。
    """
    logger = logging.getLogger("dispatcher3")
    for handler in list(logger.handlers):
        if getattr(handler, _HANDLER_FLAG, False):
            logger.removeHandler(handler)
    logger.setLevel(logging.NOTSET)
    logger.propagate = True
