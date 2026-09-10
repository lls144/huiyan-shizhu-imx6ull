# PC–Controller TCP Protocol v1

状态：M7 Desktop Linux 联调协议。它定义 PC 视觉端与未来 i.MX6ULL 控制器之间的网络边界；不定义 GPIO、LCD、FIFO 或流水线状态机实现。

## TCP framing

- 传输层为 TCP，控制器默认监听 `0.0.0.0:9000`；PC host 和 port 都是客户端配置项。
- 每个应用消息是一个 UTF-8 编码的 JSON object，末尾必须有单个 LF（`\n`）。CRLF 的 CR 会被忽略。
- 一条 TCP read 可能包含零个、一个或多个消息；实现必须按 LF 重组，不能把一次 read 当作一个消息。
- 单行上限为 16 KiB。超出上限的消息会返回 `LINE_TOO_LONG`，避免无边界缓冲。

## Common JSON schema

每个消息都必须包含以下字段：

```json
{
  "version": 1,
  "type": "enqueue",
  "request_id": "uuid-string"
}
```

`version` 必须为整数 `1`；`type` 必须为下表之一。由 PC 发起且期望响应的消息必须有唯一的 `request_id`。控制器对同一 `request_id` 的响应携带该值，供客户端匹配 Future 与 ACK。

## Message types and payload schemas

| Type | Direction | Required fields | Meaning |
|---|---|---|---|
| `enqueue` | PC → Controller | `command_id` (positive integer), `shape` (`triangle`/`rectangle`/`circle`) | 提交 M4 已去重后的语义命令。可选 `source_event_id`、`source_object_id` 为正整数。 |
| `ack` | Controller → PC | `request_id`, `status` | 对 `enqueue`、`heartbeat` 或 `reset` 的确认。`enqueue` 还返回 `command_id`。 |
| `heartbeat` | PC → Controller | `request_id` | 存活探测；控制器返回 `ack`，状态为 `alive`。 |
| `pipeline_state` | Controller → PC | `state` | 控制器状态反馈。M7 Desktop server 支持同名查询并返回 `state: "not_implemented"`，不实现 FIFO。 |
| `reset` | PC → Controller | `request_id` | 请求清除 M7 Desktop server 的重复命令记录；控制器返回 `ack`，状态为 `reset`。 |
| `error` | Controller → PC | `code`, `message` | 结构化拒绝或解析错误；若可识别请求，则同时回送 `request_id`。 |

成功 enqueue：

```json
{"version":1,"type":"ack","request_id":"...","command_id":42,"status":"accepted"}
```

同一 `command_id` 再次发送不会入队；控制器返回 `ack` 且 `status` 为 `duplicate`。M7 不连接 FIFO，因此 `accepted` 只表示网络层接受了语义命令，不表示实体动作、流水线推进或持久化。

## Error codes

| Code | Meaning |
|---|---|
| `MALFORMED_JSON` | 行不是有效 JSON object。 |
| `INVALID_MESSAGE` | 缺字段、字段类型不对、无效 `request_id` 或无效 `command_id`。 |
| `UNSUPPORTED_VERSION` | `version` 不是 `1`。 |
| `UNKNOWN_TYPE` | `type` 不在协议定义内。 |
| `INVALID_SHAPE` | enqueue 的 shape 不属于三种已支持形状。 |
| `LINE_TOO_LONG` | 单条 JSON Line 超过 16 KiB。 |

## ACK, timeout, retry and reconnect

PC client 在后台线程中连接、发送和接收。它等待带相同 `request_id` 的 `ack` 或 `error`：超时或断线时，以相同 `request_id` 与 `command_id` 有界重试；超过重试上限后 Future 失败。控制器以 `command_id` 检测重复 enqueue，因此重连后的重复发送仍是幂等的。

`heartbeat` 的 ACK 只证明 TCP 对端已处理该消息；M7 不声明 FIFO、GPIO、LCD 或流水线健康状态。`pipeline_state` 是预留状态反馈消息，M8 才定义真实状态机载荷。

## M4 / M6 compatibility

M4 的 `VisionEvent` 仅有 `OBJECT_ENTER` 才应经 M6 `CommandAdapter` 转换成语义命令；`OBJECT_EXIT` 不发送 enqueue。M7 保持 M6 的三种 shape、`command_id` 和重复语义，但以真实 localhost TCP 替代 `InMemoryLink`。这不是对已有 M1–M6 结果或 PLC 历史的修改。
