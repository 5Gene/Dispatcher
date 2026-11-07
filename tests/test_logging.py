"""日志：默认静默，打开后能看到每一步。"""
import io
import logging
import threading
import time

import pytest

import dispatcher3
from dispatcher3 import (
    action,
    disable_logging,
    dispatch,
    enable_logging,
    init_actions,
    reset,
)


@pytest.fixture
def captured(caplog):
    caplog.set_level(logging.DEBUG, logger="dispatcher3")
    return caplog


def test_silent_by_default(caplog):
    # 不调用 set_level，模拟用户没有开日志的情况
    disable_logging()
    reset()

    @action(r"^k$")
    def handler(event):
        return "k"

    init_actions()
    dispatch("k", None)

    # 默认级别是 WARNING，不主动开日志时不应有 DEBUG 记录
    assert not [r for r in caplog.records if r.name.startswith("dispatcher3")]


def test_registration_and_analysis_are_logged(captured):
    reset()

    @action(r"^user/[0-9]+$", description="查用户", priority=7)
    def handler(event):
        return event

    text = captured.text
    assert "🎬 定义 action" in text
    assert "🔍" in text and "REGEX" in text
    assert "🌀 正则层 +1" in text


def test_prefix_and_exact_are_logged(captured):
    reset()

    @action(r"^a$")
    def exact(event):
        return "a"

    @action(r"^b/.*")
    def prefix(event):
        return "b"

    text = captured.text
    assert "🎯 EXACT" in text
    assert "🧭 PREFIX" in text
    assert "🎯 精确层 +1" in text
    assert "🧭 前缀层 +1" in text


def test_finalize_report_block(captured):
    """init_actions() 要输出一张完整的 action 清单，整块用双横线包裹。"""
    reset()

    @action(r"^health$", description="健康检查", priority=100)
    def health(event):
        return "ok"

    @action(r"^api/v1/.*", description="v1 接口", priority=5)
    def api_v1(event):
        return "v1"

    @action(r"^user/[0-9]+$", description="查用户", priority=20, sync=True)
    def get_user(event):
        return "u"

    @action(r".*\.log$", description="日志文件", priority=30)
    def on_log(event):
        return "log"

    init_actions()
    text = captured.text

    lines = [line for line in text.splitlines() if line.strip()]
    block_start = next(i for i, line in enumerate(lines) if "注册表冻结" in line)
    block = "\n".join(lines[block_start - 1:])

    # 上下双横线包裹（首行前面还会带上日志前缀，所以用 in 判断）
    assert "═" * 20 in lines[block_start - 1], "块顶部应是双横线"
    assert set(lines[-1].strip()) == {"═"}, "块底部应是双横线，实际: %r" % lines[-1]

    # 汇总
    assert "共 4 个 action" in block
    assert "🎯 精确 1" in block and "🧭 前缀 1" in block
    assert "🏁 后缀 1" in block and "🌀 正则 1" in block
    assert "⚡ sync 1" in block and "· 并发 3" in block
    assert "🔐 读路径加读锁" in block

    # 表头
    for column in ("策略", "优先级", "匹配键", "处理器", "位置", "sync", "描述"):
        assert column in block, "缺少表头列: %s" % column

    # 每个 action 的全部信息都在
    for value in ("EXACT", "PREFIX", "SUFFIX", "REGEX",
                  "100", "5", "20",
                  "^health$", "^api/v1/.*", "^user/[0-9]+$",
                  "-> 'health'", "-> prefix 'api/v1/'", "-> suffix '.log'",
                  "health", "api_v1", "get_user",
                  "健康检查", "v1 接口", "查用户",
                  "test_logging.py:"):
        assert value in block, "清单里缺少: %r" % value

    # 图例
    assert "字典 O(1)" in block and "全局排他" in block


def test_finalize_report_without_sync_actions(captured):
    reset()

    @action(r"^k$")
    def handler(event):
        return "k"

    init_actions()
    assert "🚀 读路径无锁" in captured.text


def test_finalize_report_on_empty_registry(captured):
    reset()
    init_actions()
    text = captured.text
    assert "共 0 个 action" in text
    assert "（空）" in text


def test_dispatch_steps_are_logged(captured):
    reset()

    @action(r"^k$")
    def handler(event):
        return "result"

    init_actions()
    captured.clear()
    dispatch("k", None)

    text = captured.text
    assert "🎺 dispatch('k')" in text
    assert "🎯 精确命中" in text
    assert "🚀 无锁快路径" in text
    assert "▶️" in text and "执行 " in text
    assert "✅ 完成 " in text
    assert "返回 'result'" in text


def test_lock_steps_are_logged(captured):
    reset()

    @action(r"^s$", sync=True)
    def sync_handler(event):
        return "s"

    @action(r"^n$")
    def normal_handler(event):
        return "n"

    init_actions()

    captured.clear()
    dispatch("s", None)
    text = captured.text
    assert "🔑 写锁已获取（无竞争）" in text
    assert "🔓 写锁释放" in text
    assert "唤醒等待者" in text

    captured.clear()
    dispatch("n", None)
    text = captured.text
    assert "🔐 读锁 +1" in text
    assert "🔓 读锁 -1" in text


def test_exception_is_logged(captured):
    reset()

    @action(r"^boom$")
    def handler(event):
        raise ValueError("炸了")

    init_actions()
    captured.clear()
    with pytest.raises(ValueError):
        dispatch("boom", None)

    text = captured.text
    assert "💥" in text and "ValueError" in text and "炸了" in text


def test_no_match_is_logged(captured):
    reset()

    @action(r"^k$")
    def handler(event):
        return "k"

    init_actions()
    captured.clear()
    with pytest.raises(dispatcher3.NoMatchError):
        dispatch("nope", None)

    assert "❌ 没有 action 匹配" in captured.text


def test_enable_and_disable_are_idempotent():
    try:
        first = enable_logging()
        count = len(first.handlers)
        enable_logging()
        assert len(first.handlers) == count, "重复调用不应叠加 handler"
        assert first.level == logging.DEBUG
    finally:
        disable_logging()

    logger = logging.getLogger("dispatcher3")
    assert not [h for h in logger.handlers if getattr(h, "_dispatcher3_handler", False)]
    assert logger.propagate is True


# ---------------------------------------------------------------------------
# 与外部 logging 配置的交互
# ---------------------------------------------------------------------------
def test_enable_adds_own_handler_when_root_is_empty():
    """用户完全没配置 logging 时，enable_logging 自己装 handler。"""
    root = logging.getLogger()
    saved = root.handlers[:]
    root.handlers = []
    try:
        logger = enable_logging()
        handlers = [h for h in logger.handlers
                    if getattr(h, "_dispatcher3_handler", False)]
        assert len(handlers) == 1
        assert logger.propagate is False
        assert logger.level == logging.DEBUG
    finally:
        root.handlers = saved
        disable_logging()


def test_enable_defers_to_existing_root_handler():
    """调用方已经配置过 logging 时，不应再装自己的 handler，也不应重复输出。"""
    logger = enable_logging()
    assert not [h for h in logger.handlers
                if getattr(h, "_dispatcher3_handler", False)], \
        "root 已有 handler 时不应再装自己的"
    assert logger.propagate is True
    assert logger.level == logging.DEBUG


def test_disable_restores_inheritance():
    """回归：disable 后不能把级别写死成 WARNING，否则调用方之后再配置就失效。"""
    enable_logging()
    disable_logging()

    logger = logging.getLogger("dispatcher3")
    assert logger.level == logging.NOTSET, "级别应复位为 NOTSET 以继承 root"
    assert logger.propagate is True

    root = logging.getLogger()
    saved_level = root.level
    try:
        root.setLevel(logging.DEBUG)
        assert logger.getEffectiveLevel() == logging.DEBUG, \
            "disable 之后应能继承 root 的级别"
    finally:
        root.setLevel(saved_level)


def test_level_info_hides_per_dispatch_detail(captured):
    """enable_logging(INFO) 时看不到逐次分发细节。"""
    reset()

    @action(r"^k$")
    def handler(event):
        return "k"

    init_actions()
    captured.clear()
    logging.getLogger("dispatcher3").setLevel(logging.INFO)
    dispatch("k", None)

    assert "🎺 dispatch" not in captured.text


# ---------------------------------------------------------------------------
# 等锁日志
# ---------------------------------------------------------------------------
def test_write_lock_waiting_is_logged(captured):
    """一个线程持有写锁时，另一个线程等锁要能看到实时日志。"""
    import threading

    reset()
    holding = threading.Event()

    @action(r"^hold$", sync=True)
    def hold(event):
        holding.set()
        time.sleep(0.15)

    @action(r"^wait$", sync=True)
    def wait(event):
        return "w"

    init_actions()

    worker = threading.Thread(target=dispatch, args=("hold", None), name="Holder")
    worker.start()
    assert holding.wait(2.0)

    captured.clear()
    dispatch("wait", None)          # 本线程（MainThread）会等 Holder 释放写锁
    worker.join(2.0)

    text = captured.text
    assert "⏳ 写锁等待中" in text
    assert "thread=MainThread" in text
    assert "当前写者=Holder" in text
    assert "写锁已获取，全局排他中" in text
    assert "等待" in text and "ms" in text


def test_read_lock_waiting_is_logged(captured):
    """写者持锁期间，读者排队也要能看到日志。"""
    import threading

    reset()
    holding = threading.Event()

    @action(r"^hold$", sync=True)
    def hold(event):
        holding.set()
        time.sleep(0.15)

    @action(r"^read$", sync=False)
    def reader(event):
        return "r"

    init_actions()

    worker = threading.Thread(target=dispatch, args=("hold", None), name="Holder")
    worker.start()
    assert holding.wait(2.0)

    captured.clear()
    dispatch("read", None)
    worker.join(2.0)

    text = captured.text
    assert "⏳ 读锁等待中" in text
    assert "当前写者=Holder" in text
    assert "读锁 +1" in text and "等待" in text


def test_no_wait_log_when_uncontended(captured):
    """无竞争时不应出现等待日志。"""
    reset()

    @action(r"^k$", sync=True)
    def handler(event):
        return "k"

    init_actions()
    captured.clear()
    dispatch("k", None)

    assert "⏳" not in captured.text
