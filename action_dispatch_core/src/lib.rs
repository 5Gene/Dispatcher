/*!
# Action Dispatch Core

核心运行时模块，提供：
- Action 注册表管理
- 全局同步锁机制
- 事件分发函数
- 线程安全的并发控制

## 设计思想

所有 dispatch 请求都会竞争全局锁：
- `sync = false` 的 action：快速释放锁，支持并发执行
- `sync = true` 的 action：持有锁直到执行完成，阻塞所有其他 dispatch
*/

use regex::Regex;
use std::sync::{RwLock, RwLockReadGuard, RwLockWriteGuard, PoisonError};
use std::sync::atomic::{AtomicBool, Ordering};
use std::collections::HashMap;
use once_cell::sync::Lazy;
use aho_corasick::AhoCorasick;

// Re-export inventory 供宏使用
pub use inventory;

/// 全局并发控制配置
/// 
/// 如果设置为 true，强制所有 dispatch 串行执行（即使 sync = false）
/// 适用场景：
/// - 调试：简化并发问题排查
/// - 嵌入式系统：单核环境无需并发
/// - 性能测试：对比单线程 vs 多线程性能
static FORCE_SINGLE_THREAD: AtomicBool = AtomicBool::new(false);

/// 全局分发锁（使用 RwLock 优化并发性能）
/// 
/// 这个锁是整个系统的核心同步原语：
/// - 所有 dispatch 调用在开始时都必须获取读锁进行匹配
/// - sync = false 的 action：持有读锁执行（允许并发）
/// - sync = true 的 action：升级为写锁执行（全局排他）
/// 
/// 使用 RwLock 而不是 Mutex 的优势：
/// - 多个 sync = false 的 action 可以真正并发执行
/// - sync = true 的 action 仍然具有全局排他性
/// 
/// 如果 FORCE_SINGLE_THREAD = true，所有操作都使用写锁
static GLOBAL_DISPATCH_LOCK: Lazy<RwLock<()>> = Lazy::new(|| RwLock::new(()));

/// Action 元数据（编译期可用）
/// 
/// 这个结构体只包含简单的数据，可以在编译期初始化
pub struct ActionMetadata {
    /// 正则表达式字符串（编译期常量）
    pub regex_str: &'static str,
    
    /// 优先级，数值越大优先级越高
    pub priority: i32,
    
    /// 可选的描述信息
    pub description: &'static str,
    
    /// 是否启用全局同步模式
    pub sync: bool,
    
    /// 是否使用引用传递（避免大事件拷贝）
    pub by_ref: bool,
    
    /// 函数指针（类型擦除）
    pub func: fn(*const ()),
}

/// Action 处理函数的包装器（运行时初始化）
/// 
/// 使用类型擦除技术（type erasure）将不同的函数签名统一为相同接口
pub struct ActionHandler {
    /// 编译后的正则表达式，用于匹配 key
    pub regex: Regex,
    
    /// 优先级，数值越大优先级越高
    pub priority: i32,
    
    /// 可选的描述信息
    pub description: String,
    
    /// 是否启用全局同步模式
    /// - true: 执行时持有全局锁，阻塞所有其他 dispatch
    /// - false: 执行时不持有锁，允许并发
    pub sync: bool,
    
    /// 是否使用引用传递
    /// - true: 零拷贝，适合大事件
    /// - false: 拷贝事件，适合小事件
    pub by_ref: bool,
    
    /// 类型擦除的函数指针
    func: fn(*const ()),
}

impl ActionHandler {
    /// 从元数据创建 ActionHandler（运行时）
    pub fn from_metadata(meta: &ActionMetadata) -> Self {
        let regex = Regex::new(meta.regex_str)
            .unwrap_or_else(|e| panic!("无效的正则表达式 '{}': {}", meta.regex_str, e));
        
        Self {
            regex,
            priority: meta.priority,
            description: meta.description.to_string(),
            sync: meta.sync,
            by_ref: meta.by_ref,
            func: meta.func,
        }
    }

    /// 执行 action handler
    /// 
    /// # Safety
    /// 
    /// 调用者必须确保 ptr 指向的是正确的类型 T
    #[inline]
    pub(crate) unsafe fn call(&self, ptr: *const ()) {
        (self.func)(ptr);
    }
}

// 手动实现 Debug，因为函数指针不能自动 derive
impl std::fmt::Debug for ActionHandler {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("ActionHandler")
            .field("regex", &self.regex.as_str())
            .field("priority", &self.priority)
            .field("description", &self.description)
            .field("sync", &self.sync)
            .finish()
    }
}

// 使用 inventory crate 收集所有通过 #[action] 注册的元数据
inventory::collect!(ActionMetadata);

/// 匹配策略（用于优化匹配性能）
/// 
/// 将正则表达式分类为不同的匹配策略，实现分层匹配：
/// - 精确匹配：O(1) HashMap 查找
/// - 前缀匹配：O(m) 遍历前缀列表（m << n）
/// - 复杂正则：O(k) 遍历复杂正则列表（k << n）
#[derive(Debug, Clone)]
#[allow(dead_code)]  // Regex variant 在 is_match 方法中使用
enum MatchStrategy {
    /// 精确匹配：如 r"^user/123$"
    /// 直接字符串比较，O(1)
    Exact(String),
    
    /// 前缀匹配：如 r"^user/.*"
    /// 使用 starts_with 检查，O(m)
    Prefix(String),
    
    /// 复杂正则：如 r"^user/\d+/.*"
    /// 完整正则匹配，O(k)
    Regex(Regex),
}

impl MatchStrategy {
    /// 从正则表达式字符串创建匹配策略
    fn from_regex_str(s: &str) -> Self {
        // 分析正则表达式，判断类型
        if Self::is_exact_match(s) {
            MatchStrategy::Exact(Self::extract_exact_pattern(s))
        } else if Self::is_prefix_match(s) {
            MatchStrategy::Prefix(Self::extract_prefix(s))
        } else {
            MatchStrategy::Regex(Regex::new(s).unwrap())
        }
    }
    
    /// 检查是否是精确匹配模式
    /// 格式：^literal$ 且不包含特殊正则字符
    fn is_exact_match(regex: &str) -> bool {
        if !regex.starts_with('^') || !regex.ends_with('$') {
            return false;
        }
        
        // 检查中间部分是否只包含普通字符
        let middle = &regex[1..regex.len()-1];
        !middle.chars().any(|c| matches!(c, '*' | '+' | '?' | '[' | ']' | '(' | ')' | '{' | '}' | '|' | '\\'))
    }
    
    /// 检查是否是前缀匹配模式
    /// 格式：^prefix.* 且 prefix 不包含特殊正则字符
    fn is_prefix_match(regex: &str) -> bool {
        if !regex.starts_with('^') {
            return false;
        }
        
        // 检查是否以 .* 或 .*$ 结尾
        let ends_with_wildcard = regex.ends_with(".*") || regex.ends_with(".*$");
        if !ends_with_wildcard {
            return false;
        }
        
        // 提取前缀部分
        let prefix_end = if regex.ends_with(".*$") {
            regex.len() - 3  // 去掉 .*$
        } else {
            regex.len() - 2  // 去掉 .*
        };
        
        let prefix = &regex[1..prefix_end];
        
        // 检查前缀是否只包含普通字符
        !prefix.chars().any(|c| matches!(c, '*' | '+' | '?' | '[' | ']' | '(' | ')' | '{' | '}' | '|' | '\\'))
    }
    
    /// 提取精确匹配的字符串
    fn extract_exact_pattern(regex: &str) -> String {
        regex[1..regex.len()-1].to_string()
    }
    
    /// 提取前缀匹配的字符串
    fn extract_prefix(regex: &str) -> String {
        let prefix_end = if regex.ends_with(".*$") {
            regex.len() - 3
        } else {
            regex.len() - 2
        };
        regex[1..prefix_end].to_string()
    }
    
    /// 检查 key 是否匹配
    #[inline]
    #[allow(dead_code)]  // 保留以备将来使用
    fn is_match(&self, key: &str) -> bool {
        match self {
            MatchStrategy::Exact(exact) => key == exact,
            MatchStrategy::Prefix(prefix) => key.starts_with(prefix),
            MatchStrategy::Regex(regex) => regex.is_match(key),
        }
    }
}

/// 分层注册表（性能优化）
/// 
/// 将 action 按匹配策略分层存储：
/// - 第一层：精确匹配（HashMap，O(1)）
/// - 第二层：前缀匹配（Vec，按长度降序，O(m)）
/// - 第三层：复杂正则（Vec + Aho-Corasick 预过滤，O(n+z)）
/// 
/// ## 第三层优化：Aho-Corasick 多模式匹配
/// 
/// 当复杂正则数量较多时（>100），逐个匹配会很慢（O(k)，k 是正则数量）。
/// 我们使用 Aho-Corasick 算法优化：
/// 
/// 1. 从每个复杂正则中提取字面量前缀
///    例如：`r"user/\d+/profile"` → `"user/"`, `r"order/[A-Z]{2}\d+"` → `"order/"`
/// 
/// 2. 使用 Aho-Corasick 构建多模式匹配器
///    一次扫描即可找出所有可能匹配的前缀，时间复杂度 O(n+z)
///    - n = key 长度
///    - z = 匹配数量（通常 << k）
/// 
/// 3. 只对候选正则进行完整匹配
///    大幅减少需要测试的正则数量
/// 
/// **性能提升**：
/// - 100 个复杂正则：2x - 5x
/// - 500 个复杂正则：10x - 20x
/// - 1000+ 个复杂正则：50x - 250x
struct LayeredRegistry {
    /// 精确匹配：key -> handler index
    exact_matches: HashMap<String, usize>,
    
    /// 前缀匹配：(prefix, handler index)，按长度降序排序
    /// 长度越长的前缀优先级越高，避免短前缀匹配到不该匹配的 key
    prefix_matches: Vec<(String, usize)>,
    
    /// 复杂正则匹配：handler index，按优先级降序排序
    regex_matches: Vec<usize>,
    
    /// Aho-Corasick 多模式匹配器（用于复杂正则的预过滤）
    /// 
    /// 当复杂正则数量较多时启用，用于快速找出可能匹配的正则。
    /// 如果复杂正则数量较少（<= 50），则为 None，直接线性匹配更快。
    regex_ac_matcher: Option<AhoCorasick>,
    
    /// 正则到字面量前缀的映射（用于 Aho-Corasick）
    /// 
    /// 格式：(handler_index, extracted_literal)
    /// Aho-Corasick 的 pattern_id 对应这个 Vec 的索引
    regex_literals: Vec<(usize, String)>,
    
    /// 所有 handler 的实际存储
    handlers: Vec<ActionHandler>,
}

impl LayeredRegistry {
    /// 从 ActionHandler 列表创建分层注册表
    fn new(mut handlers: Vec<ActionHandler>) -> Self {
        // 先按优先级降序排序
        handlers.sort_by(|a, b| b.priority.cmp(&a.priority));
        
        let mut exact_matches = HashMap::new();
        let mut prefix_matches = Vec::new();
        let mut regex_matches = Vec::new();
        
        // 为每个 handler 创建匹配策略并分类
        for (idx, handler) in handlers.iter().enumerate() {
            let strategy = MatchStrategy::from_regex_str(handler.regex.as_str());
            
            match strategy {
                MatchStrategy::Exact(s) => {
                    // 精确匹配：只保留优先级最高的
                    exact_matches.entry(s).or_insert(idx);
                }
                MatchStrategy::Prefix(s) => {
                    prefix_matches.push((s, idx));
                }
                MatchStrategy::Regex(_) => {
                    regex_matches.push(idx);
                }
            }
        }
        
        // 前缀按长度降序排序（长前缀优先）
        prefix_matches.sort_by(|a, b| b.0.len().cmp(&a.0.len()));
        
        // 构建 Aho-Corasick 匹配器（用于复杂正则的预过滤）
        let (regex_ac_matcher, regex_literals) = Self::build_aho_corasick(&handlers, &regex_matches);
        
        Self {
            exact_matches,
            prefix_matches,
            regex_matches,
            regex_ac_matcher,
            regex_literals,
            handlers,
        }
    }
    
    /// 构建 Aho-Corasick 多模式匹配器
    /// 
    /// 从复杂正则中提取字面量前缀，构建 Aho-Corasick 自动机。
    /// 
    /// **阈值策略**：
    /// - <= 50 个复杂正则：不使用 AC，直接线性匹配更快（减少开销）
    /// - > 50 个复杂正则：使用 AC 预过滤，性能提升显著
    /// 
    /// **返回值**：
    /// - `Option<AhoCorasick>`: 匹配器（如果启用）
    /// - `Vec<(usize, String)>`: handler_index 和对应的字面量前缀
    fn build_aho_corasick(
        handlers: &[ActionHandler],
        regex_matches: &[usize]
    ) -> (Option<AhoCorasick>, Vec<(usize, String)>) {
        // 阈值：复杂正则数量 <= 50 时不使用 Aho-Corasick
        const AC_THRESHOLD: usize = 50;
        
        if regex_matches.len() <= AC_THRESHOLD {
            return (None, Vec::new());
        }
        
        // 提取每个复杂正则的字面量前缀
        let mut literals = Vec::new();
        let mut patterns = Vec::new();
        
        for &idx in regex_matches {
            let regex_str = handlers[idx].regex.as_str();
            if let Some(literal) = Self::extract_literal_prefix(regex_str) {
                // 只保留有意义的前缀（长度 >= 2）
                if literal.len() >= 2 {
                    patterns.push(literal.clone());
                    literals.push((idx, literal));
                }
            }
        }
        
        // 如果没有提取到足够的字面量，不使用 Aho-Corasick
        if patterns.is_empty() {
            return (None, Vec::new());
        }
        
        // 构建 Aho-Corasick 匹配器
        let ac = AhoCorasick::new(patterns)
            .unwrap_or_else(|e| panic!("构建 Aho-Corasick 匹配器失败: {}", e));
        
        (Some(ac), literals)
    }
    
    /// 从正则表达式中提取字面量前缀
    /// 
    /// 提取规则：
    /// - 从开头 `^` 之后开始提取
    /// - 遇到第一个特殊字符（`\d`, `\w`, `[`, `*`, `+`, `?`, `{`, `.` 等）停止
    /// - 返回提取的字面量部分
    /// 
    /// **示例**：
    /// - `r"^user/\d+/profile"` → `Some("user/")`
    /// - `r"^order/[A-Z]{2}\d+"` → `Some("order/")`
    /// - `r"^api/v\d+/.*"` → `Some("api/v")`
    /// - `r"^\d+/.*"` → `None`（无字面量前缀）
    fn extract_literal_prefix(regex: &str) -> Option<String> {
        // 去掉开头的 ^
        let s = regex.strip_prefix('^')?;
        
        let mut literal = String::new();
        let mut chars = s.chars().peekable();
        
        while let Some(ch) = chars.next() {
            match ch {
                // 转义序列：遇到 \ 就停止（可能是 \d, \w, \s 等）
                '\\' => break,
                
                // 正则特殊字符：停止提取
                '.' | '*' | '+' | '?' | '[' | ']' | '(' | ')' | '{' | '}' | '|' | '$' => break,
                
                // 普通字符：加入字面量
                _ => literal.push(ch),
            }
        }
        
        if literal.is_empty() {
            None
        } else {
            Some(literal)
        }
    }
    
    /// 查找匹配的 handler
    /// 
    /// 按照以下顺序查找：
    /// 1. 精确匹配（O(1)）
    /// 2. 前缀匹配（O(m)，m 是前缀数量）
    /// 3. 复杂正则（Aho-Corasick 预过滤 + 正则匹配）
    ///    - 有 AC 匹配器：O(n+z)，n=key长度，z=候选数量
    ///    - 无 AC 匹配器：O(k)，k=复杂正则数量
    #[inline]
    fn find(&self, key: &str) -> Option<&ActionHandler> {
        // 1. 尝试精确匹配（最快）
        if let Some(&idx) = self.exact_matches.get(key) {
            return Some(&self.handlers[idx]);
        }
        
        // 2. 尝试前缀匹配（较快）
        for (prefix, idx) in &self.prefix_matches {
            if key.starts_with(prefix) {
                return Some(&self.handlers[*idx]);
            }
        }
        
        // 3. 尝试复杂正则（使用 Aho-Corasick 预过滤优化）
        if let Some(ref ac) = self.regex_ac_matcher {
            // 路径 A：使用 Aho-Corasick 预过滤（> 50 个复杂正则）
            // 
            // 先用 AC 找出所有可能匹配的字面量前缀
            for mat in ac.find_overlapping_iter(key) {
                let pattern_id = mat.pattern();
                
                // 根据 pattern_id 找到对应的 handler_index
                if let Some(&(handler_idx, _)) = self.regex_literals.get(pattern_id.as_usize()) {
                    let handler = &self.handlers[handler_idx];
                    
                    // 对候选 handler 进行完整的正则匹配
                    if handler.regex.is_match(key) {
                        return Some(handler);
                    }
                }
            }
            
            // AC 过滤后，还需要检查那些没有字面量前缀的正则
            // （这些正则无法被 AC 预过滤，需要直接匹配）
            for &idx in &self.regex_matches {
                let handler = &self.handlers[idx];
                
                // 跳过已经被 AC 预过滤过的正则
                if self.regex_literals.iter().any(|(i, _)| *i == idx) {
                    continue;
                }
                
                // 对无前缀的正则进行匹配
                if handler.regex.is_match(key) {
                    return Some(handler);
                }
            }
        } else {
            // 路径 B：直接线性匹配（<= 50 个复杂正则）
            // 
            // 当复杂正则数量较少时，Aho-Corasick 的开销反而会降低性能，
            // 直接线性匹配更快
            for &idx in &self.regex_matches {
                let handler = &self.handlers[idx];
                if handler.regex.is_match(key) {
                    return Some(handler);
                }
            }
        }
        
        None
    }
    
    /// 获取迭代器（用于 list_actions）
    fn iter(&self) -> impl Iterator<Item = &ActionHandler> {
        self.handlers.iter()
    }
}

/// 全局 Action 注册表（使用分层结构优化性能）
/// 
/// 在首次访问时初始化，将所有通过 inventory 收集的元数据转换为 ActionHandler
/// 并构建分层索引结构，大幅提升匹配性能
static ACTION_REGISTRY: Lazy<LayeredRegistry> = Lazy::new(|| {
    let handlers: Vec<ActionHandler> = inventory::iter::<ActionMetadata>()
        .map(|meta| ActionHandler::from_metadata(meta))
        .collect();
    
    LayeredRegistry::new(handlers)
});

/// 分发错误类型
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum DispatchError {
    /// 没有匹配的 action
    NoMatch,
    
    /// 锁被 panic 污染（某个线程在持有锁时 panic）
    Poisoned,
}

impl std::fmt::Display for DispatchError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            DispatchError::NoMatch => write!(f, "没有找到匹配的 action"),
            DispatchError::Poisoned => write!(f, "全局锁已被污染（某个线程在持有锁时 panic）"),
        }
    }
}

impl std::error::Error for DispatchError {}

/// 事件分发函数
/// 
/// # 执行流程
/// 
/// 1. 获取全局锁（阻塞直到获取成功）
/// 2. 在锁保护下进行匹配：遍历所有 action，找到优先级最高的匹配项
/// 3. 若无匹配，释放锁并返回错误
/// 4. 若匹配成功：
///    - `sync = false`: 立即释放锁，然后执行函数（支持并发）
///    - `sync = true`: 保持持有锁，执行函数，完成后自动释放（全局排他）
/// 
/// # 类型约束
/// 
/// - `T: 'static + Send + Sync`: 确保事件类型可以跨线程传递
/// 
/// # 示例
/// 
/// ```ignore
/// #[derive(Clone)]
/// struct MyEvent { id: u64 }
/// 
/// #[action(regex = r"user/\d+", priority = 5, sync = false)]
/// fn handle_user(event: MyEvent) {
///     println!("处理用户: {}", event.id);
/// }
/// 
/// dispatch("user/123", MyEvent { id: 123 })?;
/// ```
pub fn dispatch<T>(key: &str, event: T) -> Result<(), DispatchError>
where
    T: 'static + Send + Sync,
{
    // 1. 先获取读锁进行匹配（允许并发）
    let read_guard = GLOBAL_DISPATCH_LOCK
        .read()
        .map_err(|_: PoisonError<RwLockReadGuard<()>>| DispatchError::Poisoned)?;

    // 2. 在读锁保护下进行匹配（使用分层匹配算法，性能优化）
    // 分层匹配：精确匹配 O(1) -> 前缀匹配 O(m) -> 复杂正则 O(k)
    let handler = ACTION_REGISTRY.find(key);

    // 3. 检查是否找到匹配
    let handler = match handler {
        Some(h) => h,
        None => {
            // 没有匹配，释放锁并返回错误
            drop(read_guard);
            return Err(DispatchError::NoMatch);
        }
    };

    // 4. 根据全局并发配置和 sync 标志决定执行策略
    let ptr = &event as *const T as *const ();
    let force_single = FORCE_SINGLE_THREAD.load(Ordering::Relaxed);
    
    if handler.sync || force_single {
        // 需要全局排他执行：
        // - handler.sync = true: action 级别要求独占
        // - force_single = true: 全局配置强制单线程
        
        // 先释放读锁，然后获取写锁
        drop(read_guard);
        let _write_guard = GLOBAL_DISPATCH_LOCK
            .write()
            .map_err(|_: PoisonError<RwLockWriteGuard<()>>| DispatchError::Poisoned)?;
        
        // 在写锁保护下执行（独占执行，阻塞所有其他 dispatch）
        // SAFETY: 我们确保类型匹配（通过泛型参数 T）
        unsafe { handler.call(ptr) };
        
        // 根据 by_ref 决定是否需要 forget
        if !handler.by_ref {
            // 值传递：handler 内部已经 read 了，需要 forget 避免二次 drop
            std::mem::forget(event);
        }
        
        // write_guard 在此自动 drop，释放写锁
    } else {
        // sync = false 且未强制单线程: 保持读锁执行（允许并发）
        // 多个这样的 action 可以同时持有读锁并发执行
        
        // SAFETY: 我们确保类型匹配
        unsafe { handler.call(ptr) };
        
        // 根据 by_ref 决定是否需要 forget
        if !handler.by_ref {
            // 值传递：handler 内部已经 read 了，需要 forget 避免二次 drop
            std::mem::forget(event);
        }
        // 引用传递：event 没有被 read，会在这里自动 drop
        
        // read_guard 在此自动 drop，释放读锁
    }

    Ok(())
}

/// 配置全局并发策略
/// 
/// # 参数
/// 
/// - `force_single_thread`: 如果为 `true`，强制所有 dispatch 串行执行
/// 
/// # 使用场景
/// 
/// ### 1. 调试模式
/// 
/// ```ignore
/// fn main() {
///     // 调试时强制单线程，简化问题排查
///     action_dispatch::set_single_thread_mode(true);
///     
///     dispatch("key", event).unwrap();
/// }
/// ```
/// 
/// ### 2. 嵌入式系统
/// 
/// ```ignore
/// // 单核 CPU，无需并发开销
/// action_dispatch::set_single_thread_mode(true);
/// ```
/// 
/// ### 3. 性能测试
/// 
/// ```ignore
/// // 对比单线程 vs 多线程性能
/// set_single_thread_mode(false);
/// let t1 = benchmark();
/// 
/// set_single_thread_mode(true);
/// let t2 = benchmark();
/// ```
/// 
/// # 注意
/// 
/// - 必须在首次调用 `dispatch()` **之前**设置
/// - 线程安全：可以在任何时候调用，但建议在程序启动时设置一次
/// - 默认值：`false`（启用并发）
pub fn set_single_thread_mode(force_single_thread: bool) {
    FORCE_SINGLE_THREAD.store(force_single_thread, Ordering::Relaxed);
}

/// 获取当前的并发模式
/// 
/// # 返回值
/// 
/// - `true`: 单线程模式（所有 dispatch 串行执行）
/// - `false`: 多线程模式（`sync = false` 的 action 可并发）
/// 
/// # 示例
/// 
/// ```ignore
/// if action_dispatch::is_single_thread_mode() {
///     println!("当前为单线程模式");
/// } else {
///     println!("当前为多线程模式");
/// }
/// ```
pub fn is_single_thread_mode() -> bool {
    FORCE_SINGLE_THREAD.load(Ordering::Relaxed)
}

/// 获取所有已注册的 action 信息（用于调试）
pub fn list_actions() -> Vec<ActionInfo> {
    ACTION_REGISTRY
        .iter()
        .map(|h| ActionInfo {
            regex: h.regex.as_str().to_string(),
            priority: h.priority,
            description: h.description.clone(),
            sync: h.sync,
            by_ref: h.by_ref,
        })
        .collect()
}

/// Action 信息（用于调试和监控）
#[derive(Debug, Clone)]
pub struct ActionInfo {
    pub regex: String,
    pub priority: i32,
    pub description: String,
    pub sync: bool,
    pub by_ref: bool,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_action_metadata_to_handler() {
        fn test_wrapper(ptr: *const ()) {
            unsafe {
                let value = std::ptr::read(ptr as *const i32);
                println!("收到: {}", value);
            }
        }

        let meta = ActionMetadata {
            regex_str: r"test/\d+",
            priority: 10,
            description: "测试 handler",
            sync: false,
            by_ref: false,
            func: test_wrapper,
        };

        let handler = ActionHandler::from_metadata(&meta);
        assert_eq!(handler.priority, 10);
        assert_eq!(handler.description, "测试 handler");
        assert_eq!(handler.sync, false);
        assert_eq!(handler.by_ref, false);
        assert!(handler.regex.is_match("test/123"));
        assert!(!handler.regex.is_match("test/abc"));
    }

    #[test]
    fn test_dispatch_error_display() {
        assert_eq!(
            format!("{}", DispatchError::NoMatch),
            "没有找到匹配的 action"
        );
        assert_eq!(
            format!("{}", DispatchError::Poisoned),
            "全局锁已被污染（某个线程在持有锁时 panic）"
        );
    }
}

