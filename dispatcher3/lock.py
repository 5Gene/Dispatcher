"""并发原语：全局读写锁 + 异步线程池。

语义
----
* sync=False 的 handler 持**读锁**执行，彼此并发
* sync=True  的 handler 持**写锁**执行，与**所有**其它 handler 互斥
  （包括 sync=False 的 handler，这才叫"全局排他"）

为什么读者也要持锁
------------------
写锁要能等到在执行的 sync=False handler 全部退出，前提是它们必须登记
自己是读者。所以"读路径无锁"和"全局排他"不可兼得，必须二选一。
本库选择全局排他 —— 这是公开承诺的语义，削弱它会把一次确定的等待
变成一场静默的数据竞争。

重入规则
--------
* 读锁可重入：sync=False handler 内嵌套 dispatch 到 sync=False action
* 写锁可重入：sync=True  handler 内嵌套 dispatch 到 sync=True  action
* 持写锁时再取读锁：允许（已持有更强的一致性）
* 持读锁时再取写锁：抛 RuntimeError。读->写升级必然死锁，明确报错
  远好于静默挂死。

写者优先
--------
有写者在等待时，新读者排队。否则持续到达的 sync=False 请求会让
sync=True 永远等不到 _readers 归零。

日志与"不在锁内做 I/O"
----------------------
临界区里绝不做 I/O —— 否则一个阻塞的日志流会把整个分发器拖死。
因此：

* 快路径的消息先收集到 notes，出锁后再输出（延迟是微秒级，无所谓）；
* **等待**路径先把锁完全释放，输出"开始等待"，再重新取锁去 wait()。
  这样等锁的线程能实时出现在日志里，而不是等完之后才补一条。
"""
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_MAX_WORKERS = 15


class GlobalLock:
    """可重入的全局读写锁，写者优先。"""

    __slots__ = ("_cond", "_readers", "_writer", "_writer_name",
                 "_write_depth", "_write_waiters", "_read_depth")

    def __init__(self) -> None:
        self._cond = threading.Condition(threading.Lock())
        self._readers = 0                        # 当前读者计数（含重入）
        self._writer: Optional[int] = None       # 持有写锁的线程 ident
        self._writer_name: Optional[str] = None
        self._write_depth = 0
        self._write_waiters = 0
        self._read_depth: Dict[int, int] = {}    # thread ident -> 读锁层数

    # -- 读 ---------------------------------------------------------------
    def acquire_read(self, trace: bool = False) -> None:
        me = threading.get_ident()
        # trace 关闭时不取线程名，避免热路径上的无谓开销
        name = threading.current_thread().name if trace else ""
        notes: List[str] = []
        must_wait = False

        with self._cond:
            depth = self._read_depth.get(me, 0)
            if depth:
                self._read_depth[me] = depth + 1
                self._readers += 1
                if trace:
                    notes.append("♻️  读锁重入 depth=%d (readers=%d) thread=%s"
                                 % (depth + 1, self._readers, name))
            elif self._writer == me:
                self._read_depth[me] = 1
                self._readers += 1
                if trace:
                    notes.append("🔐 已持写锁，读锁直接放行 (readers=%d) thread=%s"
                                 % (self._readers, name))
            elif self._writer is None and not self._write_waiters:
                self._readers += 1
                self._read_depth[me] = 1
                if trace:
                    notes.append("🔐 读锁 +1 (readers=%d) thread=%s"
                                 % (self._readers, name))
            else:
                must_wait = True

        self._flush(notes)
        if not must_wait:
            return

        # 锁已完全释放，可以安全输出，且不会拖住别的线程
        if trace:
            logger.debug("⏳ 读锁等待中… thread=%s  当前写者=%s  在读=%d  排队写者=%d",
                         name, self._writer_name or "无", self._readers,
                         self._write_waiters)
        start = time.perf_counter()

        with self._cond:
            rounds = 0
            while self._writer is not None or self._write_waiters:
                rounds += 1
                if trace and rounds > 1:
                    logger.debug("🔄 读锁被唤醒但条件不满足，继续等  thread=%s"
                                 "（写者=%s）", name, self._writer_name or "无")
                self._cond.wait()
            self._readers += 1
            self._read_depth[me] = 1
            waited = (time.perf_counter() - start) * 1000
            if trace:
                logger.debug("🔐 读锁 +1 (readers=%d) thread=%s  等待 %.3fms",
                             self._readers, name, waited)

    def release_read(self, trace: bool = False) -> None:
        me = threading.get_ident()
        # trace 关闭时不取线程名，避免热路径上的无谓开销
        name = threading.current_thread().name if trace else ""
        notes: List[str] = []

        with self._cond:
            depth = self._read_depth.get(me, 0)
            if depth == 0:
                raise RuntimeError("release_read() 与 acquire_read() 不配对")
            if depth == 1:
                del self._read_depth[me]
            else:
                self._read_depth[me] = depth - 1
            self._readers -= 1
            woke = self._readers == 0
            if trace:
                notes.append("🔓 读锁 -1 (readers=%d) thread=%s%s"
                             % (self._readers, name,
                                "  → 唤醒等待者" if woke else ""))
            if woke:
                self._cond.notify_all()

        self._flush(notes)

    # -- 写 ---------------------------------------------------------------
    def acquire_write(self, trace: bool = False) -> None:
        me = threading.get_ident()
        # trace 关闭时不取线程名，避免热路径上的无谓开销
        name = threading.current_thread().name if trace else ""
        notes: List[str] = []
        must_wait = False

        with self._cond:
            if self._writer == me:
                self._write_depth += 1
                if trace:
                    notes.append("♻️  写锁重入 depth=%d thread=%s"
                                 % (self._write_depth, name))
            elif self._read_depth.get(me):
                raise RuntimeError(
                    "不能在持有读锁时获取写锁：不要在 sync=False 的 handler 内 "
                    "dispatch 到 sync=True 的 action（读->写升级会死锁）"
                )
            elif self._writer is None and self._readers == 0:
                self._writer = me
                self._writer_name = name
                self._write_depth = 1
                if trace:
                    notes.append("🔑 写锁已获取（无竞争）thread=%s" % name)
            else:
                must_wait = True

        self._flush(notes)
        if not must_wait:
            return

        if trace:
            logger.debug("⏳ 写锁等待中… thread=%s  当前写者=%s  在读=%d  排队写者=%d",
                         name, self._writer_name or "无", self._readers,
                         self._write_waiters)
        start = time.perf_counter()

        with self._cond:
            self._write_waiters += 1
            try:
                rounds = 0
                while self._writer is not None or self._readers:
                    rounds += 1
                    if trace and rounds > 1:
                        logger.debug("🔄 写锁被唤醒但条件不满足，继续等  thread=%s"
                                     "（写者=%s, 在读=%d）",
                                     name, self._writer_name or "无", self._readers)
                    self._cond.wait()
            except BaseException:
                self._write_waiters -= 1
                self._cond.notify_all()
                raise
            self._write_waiters -= 1
            self._writer = me
            self._writer_name = name
            self._write_depth = 1
            waited = (time.perf_counter() - start) * 1000
            if trace:
                logger.debug("🔑 写锁已获取，全局排他中  thread=%s  等待 %.3fms",
                             name, waited)

    def release_write(self, trace: bool = False) -> None:
        me = threading.get_ident()
        # trace 关闭时不取线程名，避免热路径上的无谓开销
        name = threading.current_thread().name if trace else ""
        notes: List[str] = []

        with self._cond:
            if self._writer != me:
                raise RuntimeError("release_write() 与 acquire_write() 不配对")
            self._write_depth -= 1
            if self._write_depth == 0:
                self._writer = None
                self._writer_name = None
                self._cond.notify_all()
                if trace:
                    notes.append("🔓 写锁释放  thread=%s  → 唤醒等待者" % name)
            elif trace:
                notes.append("🔓 写锁重入层数 -1 (depth=%d) thread=%s"
                             % (self._write_depth, name))

        self._flush(notes)

    # -- 辅助 -------------------------------------------------------------
    @staticmethod
    def _flush(notes: List[str]) -> None:
        for note in notes:
            logger.debug(note)

    # -- 内省 -------------------------------------------------------------
    def snapshot(self):
        """返回 (readers, writer_name, write_waiters)，用于测试与诊断。"""
        with self._cond:
            return self._readers, self._writer_name, self._write_waiters


global_lock = GlobalLock()

_executor: Optional[ThreadPoolExecutor] = None
_executor_lock = threading.Lock()


def get_executor(max_workers: Optional[int] = None) -> ThreadPoolExecutor:
    """返回全局线程池，首次调用时惰性创建。

    Args:
        max_workers: 仅在首次创建时生效，后续调用忽略。
    """
    global _executor
    with _executor_lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(
                max_workers=max_workers or DEFAULT_MAX_WORKERS,
                thread_name_prefix="dispatcher",
            )
            logger.info("🏭 创建线程池 max_workers=%d", _executor._max_workers)
        return _executor


def shutdown_executor(wait: bool = True) -> None:
    """关闭全局线程池。之后调用 dispatch_async 会重新创建一个。

    Args:
        wait: 是否等待已提交的任务完成。
    """
    global _executor
    with _executor_lock:
        executor, _executor = _executor, None
    if executor is not None:
        logger.info("🏭 关闭线程池 (wait=%s)", wait)
        executor.shutdown(wait=wait)
