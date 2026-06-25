# Convenience functions that help perform actions on a remote host

## Description

Each file here is meant to implement singular functionality.
Those function like scriptlets are meant to be used in various scripts implementing concrete jobs.

If you find yourself copying the same function between various bash segments in job definitions, consider making it a scriptlet like the ones provided here.

See individual files for their purpose and usage instructions.

## Testing

The unit tests are written in [BATS (Bash automated Testing System)](https://github.com/bats-core/bats-core). To run the tests run:

```bash

cd tests
bats .
```
