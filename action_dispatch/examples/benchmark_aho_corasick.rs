/*!
性能基准测试：Aho-Corasick 优化效果

这个示例展示了 action_dispatch 在不同数量的复杂正则下的性能表现。

## 运行方式

```bash
cargo run --release --example benchmark_aho_corasick
```

## 测试说明

- 生成 N 个复杂正则 action（模拟真实场景）
- 测试 dispatch 的平均响应时间
- 对比不同规模下的性能

## 预期结果

| 复杂正则数量 | 平均 dispatch 时间 | 说明 |
|------------|------------------|------|
| 10 | 5-10 μs | 线性扫描 |
| 50 | 15-30 μs | 分界点 |
| 100 | 10-20 μs | AC 预过滤生效 ✅ |
| 300 | 15-25 μs | AC 性能优势明显 🚀 |
| 600 | 20-30 μs | 大幅优于线性扫描 🚀 |
*/

use action_dispatch::{action, dispatch, list_actions};
use std::time::{Duration, Instant};

// ============================================
// 测试用事件类型
// ============================================

#[derive(Clone, Debug)]
struct Event {
    id: u64,
    data: String,
}

// ============================================
// 动态生成 action handlers
// ============================================

// 注意：Rust 的宏在编译时执行，所以我们需要手动创建一些测试 action
// 这里我们创建多个不同前缀的复杂正则 action

macro_rules! generate_actions {
    ($($num:literal),*) => {
        $(
            paste::item! {
                #[action(regex = concat!(r"^route/", stringify!($num), r"/\d+/.*"), priority = $num)]
                fn [<handler_ $num>](event: Event) {
                    // 模拟处理逻辑
                    let _ = event.id + $num;
                }
            }
        )*
    };
}

// 生成 100 个 action（使用 paste crate 实现宏拼接）
// 由于手动生成太多代码不现实，我们这里创建代表性的测试 action

// 第一组：user 相关（模拟 RESTful API）
#[action(regex = r"^user/\d+/profile$", priority = 100)]
fn user_profile(event: Event) {
    let _ = event.id;
}

#[action(regex = r"^user/\d+/settings$", priority = 99)]
fn user_settings(event: Event) {
    let _ = event.id;
}

#[action(regex = r"^user/\d+/posts/\d+$", priority = 98)]
fn user_posts(event: Event) {
    let _ = event.id;
}

#[action(regex = r"^user/\d+/comments/\d+$", priority = 97)]
fn user_comments(event: Event) {
    let _ = event.id;
}

#[action(regex = r"^user/\d+/followers$", priority = 96)]
fn user_followers(event: Event) {
    let _ = event.id;
}

// 第二组：order 相关
#[action(regex = r"^order/[A-Z]{2}\d+$", priority = 95)]
fn order_detail(event: Event) {
    let _ = event.id;
}

#[action(regex = r"^order/\d+/items$", priority = 94)]
fn order_items(event: Event) {
    let _ = event.id;
}

#[action(regex = r"^order/\d+/payment$", priority = 93)]
fn order_payment(event: Event) {
    let _ = event.id;
}

#[action(regex = r"^order/\d+/shipping$", priority = 92)]
fn order_shipping(event: Event) {
    let _ = event.id;
}

#[action(regex = r"^order/\d+/refund$", priority = 91)]
fn order_refund(event: Event) {
    let _ = event.id;
}

// 第三组：product 相关
#[action(regex = r"^product/\d+$", priority = 90)]
fn product_detail(event: Event) {
    let _ = event.id;
}

#[action(regex = r"^product/\d+/reviews$", priority = 89)]
fn product_reviews(event: Event) {
    let _ = event.id;
}

#[action(regex = r"^product/\d+/specifications$", priority = 88)]
fn product_specs(event: Event) {
    let _ = event.id;
}

#[action(regex = r"^product/\d+/inventory$", priority = 87)]
fn product_inventory(event: Event) {
    let _ = event.id;
}

#[action(regex = r"^product/category/\w+$", priority = 86)]
fn product_category(event: Event) {
    let _ = event.id;
}

// 第四组：admin 相关
#[action(regex = r"^admin/users/\d+/ban$", priority = 85)]
fn admin_ban_user(event: Event) {
    let _ = event.id;
}

#[action(regex = r"^admin/users/\d+/unban$", priority = 84)]
fn admin_unban_user(event: Event) {
    let _ = event.id;
}

#[action(regex = r"^admin/reports/\d+$", priority = 83)]
fn admin_report(event: Event) {
    let _ = event.id;
}

#[action(regex = r"^admin/settings/[a-z_]+$", priority = 82)]
fn admin_settings(event: Event) {
    let _ = event.id;
}

#[action(regex = r"^admin/logs/\d{4}-\d{2}-\d{2}$", priority = 81)]
fn admin_logs(event: Event) {
    let _ = event.id;
}

// 第五组：api 版本相关
#[action(regex = r"^api/v1/.*$", priority = 80)]
fn api_v1(event: Event) {
    let _ = event.id;
}

#[action(regex = r"^api/v2/.*$", priority = 79)]
fn api_v2(event: Event) {
    let _ = event.id;
}

#[action(regex = r"^api/v3/.*$", priority = 78)]
fn api_v3(event: Event) {
    let _ = event.id;
}

// 第六组：notification 相关
#[action(regex = r"^notification/\d+/read$", priority = 77)]
fn notification_read(event: Event) {
    let _ = event.id;
}

#[action(regex = r"^notification/\d+/archive$", priority = 76)]
fn notification_archive(event: Event) {
    let _ = event.id;
}

#[action(regex = r"^notification/user/\d+$", priority = 75)]
fn user_notifications(event: Event) {
    let _ = event.id;
}

// 第七组：message 相关
#[action(regex = r"^message/\d+$", priority = 74)]
fn message_detail(event: Event) {
    let _ = event.id;
}

#[action(regex = r"^message/thread/\d+$", priority = 73)]
fn message_thread(event: Event) {
    let _ = event.id;
}

#[action(regex = r"^message/send/\d+$", priority = 72)]
fn message_send(event: Event) {
    let _ = event.id;
}

// 第八组：search 相关
#[action(regex = r"^search/products/.*$", priority = 71)]
fn search_products(event: Event) {
    let _ = event.id;
}

#[action(regex = r"^search/users/.*$", priority = 70)]
fn search_users(event: Event) {
    let _ = event.id;
}

#[action(regex = r"^search/orders/.*$", priority = 69)]
fn search_orders(event: Event) {
    let _ = event.id;
}

// 更多 action...
// （在真实场景中可能有数百个）

// ============================================
// 性能测试函数
// ============================================

/// 运行性能基准测试
fn benchmark(name: &str, keys: &[&str], iterations: usize) {
    println!("\n┌─────────────────────────────────────────────────────");
    println!("│ 测试：{}", name);
    println!("├─────────────────────────────────────────────────────");
    
    let event = Event {
        id: 123,
        data: "test data".to_string(),
    };
    
    // 预热（确保惰性初始化完成）
    for key in keys {
        let _ = dispatch(key, event.clone());
    }
    
    // 正式测试
    let start = Instant::now();
    for _ in 0..iterations {
        for key in keys {
            let _ = dispatch(key, event.clone());
        }
    }
    let elapsed = start.elapsed();
    
    let total_dispatches = iterations * keys.len();
    let avg_time = elapsed / total_dispatches as u32;
    let throughput = (total_dispatches as f64 / elapsed.as_secs_f64()) as u64;
    
    println!("│");
    println!("│ 总 dispatch 次数:  {}", total_dispatches);
    println!("│ 总耗时:            {:?}", elapsed);
    println!("│ 平均 dispatch 时间: {:?}", avg_time);
    println!("│ 吞吐量:            {} dispatch/s", throughput);
    println!("└─────────────────────────────────────────────────────\n");
}

// ============================================
// 主函数
// ============================================

fn main() {
    println!("\n🚀 action_dispatch 性能基准测试：Aho-Corasick 优化");
    println!("═══════════════════════════════════════════════════════\n");
    
    // 显示已注册的 action 数量
    let actions = list_actions();
    let mut exact_count = 0;
    let mut prefix_count = 0;
    let mut regex_count = 0;
    
    for action in &actions {
        let regex_str = &action.regex; // 修复点：改为借用
        if regex_str.starts_with('^') && regex_str.ends_with('$') 
            && !regex_str.contains(r"\d") 
            && !regex_str.contains('[') 
            && !regex_str.contains('*') 
            && !regex_str.contains('+') {
            exact_count += 1;
        } else if regex_str.ends_with(".*") || regex_str.ends_with(".*$") {
            prefix_count += 1;
        } else {
            regex_count += 1;
        }
    }
    
    println!("📊 已注册 action 统计");
    println!("─────────────────────────────────────────────────────");
    println!("  总数:         {} 个", actions.len());
    println!("  精确匹配:     {} 个 (HashMap O(1))", exact_count);
    println!("  前缀匹配:     {} 个 (Vec O(m))", prefix_count);
    println!("  复杂正则:     {} 个", regex_count);
    println!();
    
    if regex_count > 50 {
        println!("  ✅ Aho-Corasick 优化已启用（复杂正则 > 50）");
    } else {
        println!("  ⚪ Aho-Corasick 未启用（复杂正则 ≤ 50）");
    }
    println!("─────────────────────────────────────────────────────\n");
    
    // 测试场景 1：匹配存在的 key
    let test_keys = vec![
        "user/123/profile",
        "order/AB1234",
        "product/456",
        "admin/users/789/ban",
        "api/v2/anything",
        "notification/111/read",
        "message/222",
        "search/products/laptop",
    ];
    
    benchmark(
        "常规请求（所有 key 都能匹配）",
        &test_keys,
        10_000
    );
    
    // 测试场景 2：混合匹配和不匹配
    let mixed_keys = vec![
        "user/123/profile",      // ✅ 匹配
        "nonexistent/path",      // ❌ 不匹配
        "order/AB1234",          // ✅ 匹配
        "invalid/route",         // ❌ 不匹配
        "product/456",           // ✅ 匹配
    ];
    
    benchmark(
        "混合请求（部分匹配，部分不匹配）",
        &mixed_keys,
        10_000
    );
    
    // 测试场景 3：最坏情况（key 总是匹配最后一个）
    let worst_case_keys = vec![
        "search/orders/anything",  // 匹配最后的 search/orders 正则
    ];
    
    benchmark(
        "最坏情况（匹配最后的正则）",
        &worst_case_keys,
        10_000
    );
    
    // 测试场景 4：最好情况（key 总是匹配第一个）
    let best_case_keys = vec![
        "user/123/profile",  // 优先级最高的正则
    ];
    
    benchmark(
        "最好情况（匹配最高优先级正则）",
        &best_case_keys,
        10_000
    );
    
    println!("\n📈 性能分析");
    println!("═══════════════════════════════════════════════════════");
    println!();
    println!("预期结果：");
    println!();
    println!("  如果复杂正则数量 > 50：");
    println!("    - Aho-Corasick 预过滤生效");
    println!("    - 平均 dispatch 时间应该在 1-30 μs");
    println!("    - 吞吐量应该在 50K-1M dispatch/s");
    println!();
    println!("  如果复杂正则数量 ≤ 50：");
    println!("    - 使用线性扫描");
    println!("    - 平均 dispatch 时间取决于匹配位置");
    println!("    - 吞吐量应该在 10K-500K dispatch/s");
    println!();
    println!("对比说明：");
    println!("  - 当前示例只有 {} 个复杂正则", regex_count);
    if regex_count > 50 {
        println!("  - ✅ AC 优化生效，性能应该很好");
    } else {
        println!("  - ⚪ 复杂正则较少，线性扫描足够快");
        println!("  - 💡 要测试 AC 优化效果，需要增加更多复杂正则 action");
    }
    println!("═══════════════════════════════════════════════════════\n");
}

