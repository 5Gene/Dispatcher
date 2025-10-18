/*!
集成测试：验证 action_dispatch 系统的各项功能
*/

use action_dispatch::{action, dispatch, DispatchError};
use std::sync::atomic::{AtomicU32, Ordering};
use std::sync::Arc;
use std::thread;
use std::time::Duration;

#[derive(Clone, Debug)]
struct TestEvent {
    value: u32,
}

// 测试用的全局计数器
static TEST_COUNTER: AtomicU32 = AtomicU32::new(0);

#[action(regex = r"test/basic", priority = 0)]
fn test_basic_handler(event: TestEvent) {
    TEST_COUNTER.fetch_add(event.value, Ordering::SeqCst);
}

#[action(regex = r"test/priority/low", priority = 1)]
fn test_priority_low(_event: TestEvent) {
    TEST_COUNTER.store(100, Ordering::SeqCst);
}

#[action(regex = r"test/priority/high", priority = 10)]
fn test_priority_high(_event: TestEvent) {
    TEST_COUNTER.store(200, Ordering::SeqCst);
}

// 匹配相同 key 但优先级更高
#[action(regex = r"test/priority/.*", priority = 5)]
fn test_priority_medium(_event: TestEvent) {
    TEST_COUNTER.store(150, Ordering::SeqCst);
}

#[action(regex = r"test/sync", priority = 0, sync = true)]
fn test_sync_handler(event: TestEvent) {
    thread::sleep(Duration::from_millis(100));
    TEST_COUNTER.fetch_add(event.value, Ordering::SeqCst);
}

#[test]
fn test_basic_dispatch() {
    TEST_COUNTER.store(0, Ordering::SeqCst);

    let result = dispatch("test/basic", TestEvent { value: 42 });
    assert!(result.is_ok());
    assert_eq!(TEST_COUNTER.load(Ordering::SeqCst), 42);
}

#[test]
fn test_no_match() {
    let result = dispatch("nonexistent/key", TestEvent { value: 1 });
    assert!(matches!(result, Err(DispatchError::NoMatch)));
}

#[test]
fn test_priority() {
    // 测试低优先级
    TEST_COUNTER.store(0, Ordering::SeqCst);
    dispatch("test/priority/low", TestEvent { value: 0 }).unwrap();
    // 应该匹配 priority = 5 的 medium，而不是 priority = 1 的 low
    assert_eq!(TEST_COUNTER.load(Ordering::SeqCst), 150);

    // 测试高优先级
    TEST_COUNTER.store(0, Ordering::SeqCst);
    dispatch("test/priority/high", TestEvent { value: 0 }).unwrap();
    // 应该匹配 priority = 10 的 high
    assert_eq!(TEST_COUNTER.load(Ordering::SeqCst), 200);
}

#[test]
fn test_concurrent_dispatch() {
    TEST_COUNTER.store(0, Ordering::SeqCst);

    let handles: Vec<_> = (0..10)
        .map(|_| {
            thread::spawn(|| {
                dispatch("test/basic", TestEvent { value: 1 }).unwrap();
            })
        })
        .collect();

    for h in handles {
        h.join().unwrap();
    }

    assert_eq!(TEST_COUNTER.load(Ordering::SeqCst), 10);
}

#[test]
fn test_sync_blocking() {
    TEST_COUNTER.store(0, Ordering::SeqCst);

    // 启动多个线程，都调用 sync = true 的 handler
    // 由于全局锁，它们应该串行执行
    let start = std::time::Instant::now();
    
    let handles: Vec<_> = (0..3)
        .map(|_| {
            thread::spawn(|| {
                dispatch("test/sync", TestEvent { value: 1 }).unwrap();
            })
        })
        .collect();

    for h in handles {
        h.join().unwrap();
    }

    let elapsed = start.elapsed();

    // 验证结果
    assert_eq!(TEST_COUNTER.load(Ordering::SeqCst), 3);
    
    // 由于每个 handler 睡眠 100ms，3 个串行执行至少需要 300ms
    assert!(
        elapsed >= Duration::from_millis(300),
        "串行执行时间过短: {:?}",
        elapsed
    );
}

#[test]
fn test_regex_patterns() {
    // 测试正则表达式匹配
    TEST_COUNTER.store(0, Ordering::SeqCst);

    // 匹配成功
    assert!(dispatch("test/basic", TestEvent { value: 10 }).is_ok());
    assert_eq!(TEST_COUNTER.load(Ordering::SeqCst), 10);

    // 匹配失败
    assert!(matches!(
        dispatch("test/basic/extra", TestEvent { value: 1 }),
        Err(DispatchError::NoMatch)
    ));
}

#[test]
fn test_list_actions() {
    let actions = action_dispatch::list_actions();
    
    // 应该至少有我们定义的几个 action
    assert!(!actions.is_empty());
    
    // 验证按优先级排序（降序）
    for i in 1..actions.len() {
        assert!(
            actions[i - 1].priority >= actions[i].priority,
            "actions 应该按优先级降序排列"
        );
    }
}

