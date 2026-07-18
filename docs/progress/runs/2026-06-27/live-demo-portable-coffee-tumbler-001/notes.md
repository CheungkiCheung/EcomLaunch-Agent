# Notes

- This was a real gateway/runtime/model run, not a replay or mocked LLM.
- The run used authenticated API access, CSRF, `agent_name=ecom-launch`, `mode=ultra`, `subagent_enabled=true`, and live DeepSeek model calls.
- Public fixture files were staged in the thread uploads directory.
- The agent ignored the practical need to stay bounded and entered repeated public web search/fetch loops.
- The run did not produce artifacts, did not call `present_files`, and failed validator acceptance.
- The failure changed the contract: benchmark-fixture runs must use uploaded fixtures first and avoid broad external web search unless explicitly requested.
