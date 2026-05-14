# Phase 06: Reachability Backend

## Goal

实现 `ReachabilityBackend` 第一版子类 `PiperDexechainReachabilityBackend`。可达性只作为提示信息，不删除 episode、不裁剪帧。

## Scope

- 输入以 `PolicyEpisode` 为第一版标准输入。
- 在可视化前计算当前轨迹 IK 可达性。
- 输出 `ReachabilityReport` 和前端 `ReachabilityOverlay`。
- 第一版内部接入当前 dexechain/Piper IK 逻辑。
- 前端在轨迹和时间轴展示可达/不可达帧。
- 报告只要求能被当前工具消费，不要求完整保留旧 `filter_report.json` 所有字段。

## Acceptance

- 对一个 `PolicyEpisode` 能返回每帧 reachable/unreachable 标记。
- 前端可在轨迹可视化中看到不可达帧位置。
- 可达性结果只影响展示，不改变 accepted/rejected 状态，不删除数据。
- dexechain 依赖只存在于 `PiperDexechainReachabilityBackend` 或 compat 层。
- 可用 mock backend 在无 dexechain 环境下验证前端 overlay。

## Tests

- Mock backend test：固定输入返回固定 overlay。
- Piper backend smoke test：对一条小型 episode 运行可达性检查。
- UI overlay test：前端显示 reachable/unreachable 标记。
- Dependency boundary test：core reachability model 不 import dexechain/embodichain。

## Out Of Scope

- 不实现自研 IK。
- 不支持通用 URDF IK。
- 不根据可达性自动剔除 episode 或帧。
