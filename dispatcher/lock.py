# ============================================================================
# 优化 2：快速路径 RWLock
# ============================================================================
import concurrent.futures
import threading
from concurrent.futures import Future
LOG = False

class FastRWLock:
    """
    优化的读写锁

    优化：
    - 快速路径：无竞争时避免条件变量
    - 使用原子操作（在 Python 中用简单的整数）
    数据一致性保护
    - 读锁（read lock）只允许并发读取，但不能防止其他线程同时读取
    - 写锁（write lock）是独占的，确保在修改数据时没有其他线程在读取或写入
    """
    __slots__ = ('_lock', '_read_ready', '_readers', '_writers', '_write_waiters')

    def _log(self, msg):
        if not LOG:
            return
        print(f"{threading.current_thread().name} {msg}")

    def __init__(self):
        self._lock = threading.Lock()
        self._read_ready = threading.Condition(self._lock)
        self._readers = 0
        self._writers = 0
        self._write_waiters = 0

    def acquire_read(self):
        """快速路径优化的读锁获取"""
        # 尝试快速路径（无写入时）
        with self._lock:
            # 快速检查：无写入者和等待写入者
            if self._writers == 0 and self._write_waiters == 0:
                self._readers += 1
                return

            # 慢路径：有竞争
            while self._writers > 0 or self._write_waiters > 0:
                self._log(f"🔒 acquire_read -> 慢路径：有竞争，等【写锁】==>_writers:{self._writers}")
                self._read_ready.wait()
            self._readers += 1

    def release_read(self):
        """释放读锁"""
        with self._lock:
            self._readers -= 1
            self._log(f"🔒 release_read -> 释放读锁 ==>_readers:{self._readers}")
            if self._readers == 0:
                self._read_ready.notify_all()

    def acquire_write(self,key):
        """获取写锁"""
        with self._lock:
            self._write_waiters += 1
            try:
                while self._readers > 0 or self._writers > 0:
                    self._log(f"🔒 acquire_write -> 慢路径：有竞争【{key}】等待【写锁】 ==> _readers:{self._readers} >> _writers:{self._writers}")
                    self._read_ready.wait()
                self._log(f"🔒 acquire_write ->【{key}】获取并持有【写锁】 ==> _readers:{self._readers} >> _writers:{self._writers}")
                self._writers += 1
                self._write_waiters -= 1
            except:
                self._write_waiters -= 1
                raise

    def release_write(self):
        """释放写锁"""
        with self._lock:
            self._writers -= 1
            self._log(f"🔒 release_read -> 释放写锁 ==>_writers:{self._writers}")
            self._read_ready.notify_all()


global_rw_lock = FastRWLock()

global_executor = concurrent.futures.ThreadPoolExecutor(max_workers=15)