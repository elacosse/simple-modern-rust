//! Reusable application logic.

/// Returns a greeting for `name`.
///
/// ```
/// assert_eq!(simple_modern_rust::greet("Rust"), "Hello, Rust!");
/// ```
pub fn greet(name: &str) -> String {
    format!("Hello, {name}!")
}

#[cfg(test)]
mod tests {
    #[test]
    fn greets_name() {
        assert_eq!(super::greet("Ada"), "Hello, Ada!");
    }
}
