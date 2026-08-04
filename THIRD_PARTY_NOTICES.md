# Third-party notices

OpenSKU contains and extends open-source software. The repository's [MIT License](LICENSE) covers OpenSKU's original contributions. Required notices for incorporated upstream code are retained below.

## Core upstream project

Parts of the agent harness, backend runtime, frontend foundation, deployment configuration, and compatibility namespaces originated from [DeerFlow](https://github.com/bytedance/deer-flow), Copyright (c) 2025 Bytedance Ltd. and/or its affiliates and Copyright (c) 2025-2026 DeerFlow Authors, under the MIT License reproduced below.

OpenSKU's product positioning, ecommerce launch workflows, Growth Analyst, evidence contract, run-budget behavior, bilingual product experience, War Room implementation, room artwork, and character assets are project-specific additions or modifications.

Some internal compatibility identifiers still use names such as `deerflow`, `DEER_FLOW_*`, `.deer-flow`, and `ecom-launch`. They are retained where changing them would break package imports, environment contracts, stored state, Docker resources, or existing thread ownership. They are not the public product brand.

## Additional open-source work

Product-management skill material was adapted from [phuryn/pm-skills](https://github.com/phuryn/pm-skills) under its applicable license and attribution terms. Individual dependencies retain their own licenses and notices in their distributed packages and lockfiles.

This notice is informational and does not replace the license text of any dependency.

## Upstream MIT license

```text
MIT License

Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
Copyright (c) 2025-2026 DeerFlow Authors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
