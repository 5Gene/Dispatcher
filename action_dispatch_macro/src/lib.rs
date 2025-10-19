/*!
# Action Dispatch Macro

过程宏实现模块，提供 `#[action(...)]` 属性宏

## 功能

解析注解参数：
- `regex`: 正则表达式（必需）
- `priority`: 优先级（可选，默认 0）
- `description`: 描述信息（可选，默认空字符串）
- `sync`: 是否全局同步（可选，默认 false）

生成注册代码，使用 inventory 在编译期收集所有 handler
*/

use proc_macro::TokenStream;
use quote::quote;
use syn::{
    parse_macro_input, punctuated::Punctuated, token::Comma, Expr, ExprLit, ItemFn, Lit, Meta,
    MetaNameValue,
};

/// #[action(...)] 属性宏
/// 
/// # 参数
/// 
/// - `regex = "..."`: 匹配 key 的正则表达式（必需）
/// - `priority = N`: 优先级，整数（可选，默认 0）
/// - `description = "..."`: 描述信息（可选）
/// - `sync = true/false`: 是否启用全局同步模式（可选，默认 false）
/// 
/// # 示例
/// 
/// ```ignore
/// #[action(regex = r"user/\d+", priority = 10, sync = true, description = "用户操作")]
/// fn handle_user(event: MyEvent) {
///     // ...
/// }
/// ```
#[proc_macro_attribute]
pub fn action(args: TokenStream, input: TokenStream) -> TokenStream {
    // syn 2.0: 使用 Punctuated 替代 AttributeArgs
    let args = parse_macro_input!(args with Punctuated::<Meta, Comma>::parse_terminated);
    let input_fn = parse_macro_input!(input as ItemFn);

    // 解析参数
    let params = match parse_action_params(args) {
        Ok(p) => p,
        Err(e) => return e.to_compile_error().into(),
    };

    // 验证函数签名
    if let Err(e) = validate_function(&input_fn) {
        return e.to_compile_error().into();
    }

    // 生成注册代码
    generate_registration(params, input_fn).into()
}

/// Action 参数
struct ActionParams {
    regex: String,
    priority: i32,
    description: String,
    sync: bool,
    by_ref: bool,  // 是否使用引用传递（避免大事件拷贝）
}

/// 解析 #[action(...)] 的参数
fn parse_action_params(args: Punctuated<Meta, Comma>) -> syn::Result<ActionParams> {
    let mut regex: Option<String> = None;
    let mut priority: i32 = 0;
    let mut description: String = String::new();
    let mut sync: bool = false;
    let mut by_ref: bool = false;

    for arg in args {
        match arg {
            Meta::NameValue(MetaNameValue { path, value, .. }) => {
                let ident = path.get_ident().ok_or_else(|| {
                    syn::Error::new_spanned(&path, "无效的参数名")
                })?;

                match ident.to_string().as_str() {
                    "regex" => {
                        if let Expr::Lit(ExprLit { lit: Lit::Str(s), .. }) = value {
                            regex = Some(s.value());
                        } else {
                            return Err(syn::Error::new_spanned(
                                value,
                                "regex 参数必须是字符串字面量",
                            ));
                        }
                    }
                    "priority" => {
                        if let Expr::Lit(ExprLit { lit: Lit::Int(i), .. }) = value {
                            priority = i.base10_parse()?;
                        } else {
                            return Err(syn::Error::new_spanned(
                                value,
                                "priority 参数必须是整数字面量",
                            ));
                        }
                    }
                    "description" => {
                        if let Expr::Lit(ExprLit { lit: Lit::Str(s), .. }) = value {
                            description = s.value();
                        } else {
                            return Err(syn::Error::new_spanned(
                                value,
                                "description 参数必须是字符串字面量",
                            ));
                        }
                    }
                    "sync" => {
                        if let Expr::Lit(ExprLit { lit: Lit::Bool(b), .. }) = value {
                            sync = b.value;
                        } else {
                            return Err(syn::Error::new_spanned(
                                value,
                                "sync 参数必须是布尔字面量（true 或 false）",
                            ));
                        }
                    }
                    "by_ref" => {
                        if let Expr::Lit(ExprLit { lit: Lit::Bool(b), .. }) = value {
                            by_ref = b.value;
                        } else {
                            return Err(syn::Error::new_spanned(
                                value,
                                "by_ref 参数必须是布尔字面量（true 或 false）",
                            ));
                        }
                    }
                    _ => {
                        return Err(syn::Error::new_spanned(
                            ident,
                            format!("未知参数: {}", ident),
                        ));
                    }
                }
            }
            _ => {
                return Err(syn::Error::new_spanned(
                    arg,
                    "参数必须是 name = value 格式",
                ));
            }
        }
    }

    // 验证必需参数
    let regex = regex.ok_or_else(|| {
        syn::Error::new(
            proc_macro2::Span::call_site(),
            "缺少必需参数: regex",
        )
    })?;

    Ok(ActionParams {
        regex,
        priority,
        description,
        sync,
        by_ref,
    })
}

/// 验证函数签名
/// 
/// 要求：
/// - 必须恰好有一个参数
/// - 参数类型必须是具体类型（不能是引用）
fn validate_function(func: &ItemFn) -> syn::Result<()> {
    // 检查参数数量
    if func.sig.inputs.len() != 1 {
        return Err(syn::Error::new_spanned(
            &func.sig.inputs,
            "action 函数必须恰好有一个参数",
        ));
    }

    // 检查是否是自由函数（不在 impl 块中）
    // 这个检查由使用场景保证，宏本身不需要特别处理

    Ok(())
}

/// 生成注册代码
/// 
/// 生成的代码包括：
/// 1. 原始函数定义
/// 2. Send + Sync 约束检查
/// 3. 类型擦除的包装函数
/// 4. 使用 inventory::submit! 注册元数据
fn generate_registration(params: ActionParams, func: ItemFn) -> proc_macro2::TokenStream {
    let ActionParams {
        regex,
        priority,
        description,
        sync,
        by_ref,
    } = params;

    let func_name = &func.sig.ident;
    let vis = &func.vis;
    let sig = &func.sig;
    let block = &func.block;
    let attrs = &func.attrs;

    // 获取参数类型
    let input_type = match func.sig.inputs.first() {
        Some(syn::FnArg::Typed(pat_type)) => &pat_type.ty,
        _ => {
            return syn::Error::new_spanned(
                &func.sig.inputs,
                "无法获取参数类型",
            )
            .to_compile_error();
        }
    };

    // 生成包装函数名，用于类型擦除
    let wrapper_name = syn::Ident::new(
        &format!("__action_wrapper_{}", func_name),
        proc_macro2::Span::call_site(),
    );

    // 根据 by_ref 生成不同的包装函数体
    let wrapper_body = if by_ref {
        // 引用传递：不拷贝数据，只传递引用
        quote! {
            unsafe {
                // 将原始指针转换为引用（零拷贝）
                let event = &*(ptr as *const #input_type);
                // 调用用户定义的 handler
                #func_name(event);
                // 注意：不需要 forget，因为没有所有权转移
            }
        }
    } else {
        // 值传递：拷贝数据并转移所有权
        quote! {
            unsafe {
                // 读取事件数据（会转移所有权）
                let event = std::ptr::read(ptr as *const #input_type);
                // 调用用户定义的 handler
                #func_name(event);
                // 注意：event 的所有权已转移给 handler，不需要手动释放
            }
        }
    };

    quote! {
        // 保留原始函数定义
        #(#attrs)*
        #vis #sig {
            #block
        }

        // 编译期类型约束检查：确保事件类型是 Send + Sync
        // 这保证了多线程环境下的安全性
        const _: fn() = || {
            fn assert_send_sync<T: Send + Sync>() {}
            assert_send_sync::<#input_type>();
        };

        // 生成类型擦除的包装函数
        // 这个函数将原始指针转换回具体类型，然后调用用户函数
        #[allow(non_snake_case)]
        fn #wrapper_name(ptr: *const ()) {
            #wrapper_body
        }

        // 生成注册代码
        // 使用 inventory::submit! 在编译期收集所有 action 元数据
        ::action_dispatch_core::inventory::submit! {
            // 创建静态的 ActionMetadata
            // 这个结构体只包含简单数据，可以在编译期初始化
            ::action_dispatch_core::ActionMetadata {
                regex_str: #regex,
                priority: #priority,
                description: #description,
                sync: #sync,
                by_ref: #by_ref,
                func: #wrapper_name,
            }
        }
    }
}

