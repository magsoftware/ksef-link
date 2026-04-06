# Python Code Quality Review

This file is a review checklist, not a second style guide.
It must be applied together with `.ai/coding-style.md`.
If there is any conflict, `.ai/coding-style.md` wins.

## Architecture & Design

1. **SOLID Principles**
   - Single Responsibility: Does each class/function do one thing well?
   - Apply abstraction only when justified by the current codebase and requirements.
   - Prefer small, direct designs over framework-style indirection.

2. **Design Patterns**
   - No over-engineering or pattern abuse
   - Clean separation of concerns
   - Do not introduce patterns unless they clearly improve the current code

3. **Code Organization**
   - Logical module structure
   - Clear public/private boundaries
   - No circular dependencies
   - Appropriate abstraction levels
   - Prefer small functions, but optimize for clarity over arbitrary limits

## Pythonic Idioms

1. **Modern Python Features**
   - Use newer syntax only when it improves readability
   - Do not force walrus operator or pattern matching into otherwise clear code
   - f-strings over `.format()` or `%`
   - `pathlib` over `os.path`
   - `dataclasses` for data containers

2. **Comprehensions & Generators**
   - List/dict/set comprehensions used appropriately
   - Generator expressions for memory efficiency
   - No overly complex nested comprehensions

3. **Context Managers**
   - `with` statements for resource handling
   - Custom context managers where appropriate
   - No resource leaks

4. **Itertools & Functools**
   - Use `itertools` or `functools` only when they make code clearer
   - Avoid cleverness that reduces maintainability

## Type Safety

1. **Type Hints**
   - All function signatures typed
   - Return types specified
   - Complex types properly annotated

2. **Type Patterns**
   - `Optional[T]` or `T | None` used correctly
   - `TypeVar`, `Protocol`, `Literal`, and `TypedDict` only when they materially improve correctness
   - No unnecessary type complexity

3. **Type Narrowing**
   - Proper use of `isinstance()` checks
   - `assert` for type narrowing where safe
   - No `Any` type abuse (audit each usage)

## Error Handling

1. **Exception Patterns**
   - Specific exception types (never bare `except:`)
   - Exception chaining (`raise ... from`)
   - Custom exceptions for domain errors

2. **Error Recovery**
   - Graceful degradation where appropriate
   - Clear error messages
   - Proper logging of errors
   - No swallowed exceptions
