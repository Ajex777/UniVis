## P1: Dexforce W1 Teleoperation Adapter

### WHY

接下来需要将 dexforce_w1 遥操数据接入 UniVis，使它可以像 PIKA raw、HDF5、LeRobot V3 一样被统一可视化、标注和质量检测。

参考脚本：

- `/home/dex/app/embodichain/dexechain/data/scripts/tele2hdf5/tele2hdf5.sh`
- `/home/dex/app/embodichain/dexechain/data/scripts/tele2hdf5/w1_telecontrol_to_hdf5.py`

当前 `tele2hdf5` 链路做了如下处理：

1. 遍历数据根目录下的每个遥操 episode 目录。
2. 读取 `metadata.jsonl`，筛选并排序图像帧时间戳。
3. 读取 `pose_record_*.json` 中的 qpos 关节角数据。
4. 将 qpos 插值到图像时间戳。
5. 对 gripper/dextrous hand 做简单尺度处理。
6. 将图像、infrared、qpos、action 和语言标注写入 compressed HDF5。

但是 UniVis 的统一中间格式是 `PolicyEpisode`，其双臂轨迹字段是 EEF pose：

- `left.xyz`
- `left.rot6d`
- `left.gripper`
- `right.xyz`
- `right.rot6d`
- `right.gripper`

dexforce_w1 遥操数据保存的是 qpos，因此 adapter 不能只复用 HDF5 转换脚本。它需要在加载 episode 时读取全量 qpos，并通过 W1 专用 FK 将全身状态中的双臂相关关节转成 EEF pose。

注意：W1 是人形机器人，不是单纯的双臂机器人。虽然 `PolicyEpisode` 当前只展示双臂 EEF pose + gripper，但 adapter 内部不能只读取双臂 qpos。它必须保留完整 qpos，因为 W1 的 FK 可能依赖腰部、躯干或其他全身状态。经过重新评估，第一版不再拆出全局通用 FK/IK 接口；FK 先作为 `formats/dexforce_w1_teleop` 下的 W1 专用实现，IK 暂不实现。

### Design Principles

1. `DexforceW1TeleopAdapter` 负责读取和同步遥操数据，并调用同 format 内部的 W1 FK 工具生成 EEF pose。
2. 第一版不设计全局 `univis.kinematics` 抽象，也不实现 IK，避免在 W1 全身运动学尚未稳定前过早抽象。
3. W1 FK 放在 `formats/dexforce_w1_teleop` 内部，作为该 format 的专用能力；后续若有多个机器人共享需求，再考虑抽象为通用 kinematics 模块。
4. adapter 必须读取完整 qpos，不只读取双臂 qpos；双臂/腰部/head/hand 等 joint order 都应由 yaml 配置描述。
5. camera layout、时间同步策略、qpos joint order、FK 参数都应放在 `formats/dexforce_w1_teleop/config/default.yaml` 中，不要硬编码在 adapter 里。
6. 输出到 `PolicyEpisode` 后，DTW、smooth、HDF5 exporter 等功能应无需感知数据来自 dexforce_w1。

## Raw Data Assumption

第一版按现有 `tele2hdf5` 脚本识别如下结构。

每个 episode 目录包含：

- `metadata.jsonl`
- `pose_record_*.json`
- `head/left/<image>`
- `head/right/<image>`
- `hand/left/<image>`
- `hand/right/<image>`
- 可选 infrared 数据，例如 `hand/left_infra1`、`hand/right_infra2`

`pose_record_*.json` 中 qpos 默认 joint order 参考 `W1_TELEOPS_JOINTS_ORDER`：

- body/head: `ANKLE`, `KNEE`, `BUTTOCK`, `WAIST`, `NECK1`, `NECK2`
- left arm: `LEFT_J1` 到 `LEFT_J7`
- left gripper: `LEFT_GRIPPER`
- right arm: `RIGHT_J1` 到 `RIGHT_J7`
- right gripper: `RIGHT_GRIPPER`
- optional dextrous hand joints

第一版 UniVis 对外仍只需要产出双臂 EEF pose + gripper：

- left arm qpos indices: `[6, 7, 8, 9, 10, 11, 12]`
- left gripper index: `[13]`
- right arm qpos indices: `[14, 15, 16, 17, 18, 19, 20]`
- right gripper index: `[21]`

但 adapter 内部的同步结果应保留全量 qpos。上述索引只用于从全量 qpos 中取出 FK 所需的 control joints 和 gripper 值，不代表 adapter 可以丢弃其他 joints。

这些 joint 名称和索引应来自 yaml 配置，而不是从 dexechain enum 运行时导入。

## Proposed Modules

### `univis.formats.dexforce_w1_teleop.fk`

定义 W1 专用 FK 工具，而不是通用 kinematics backend。

该工具应从 dexechain 现有 FK 逻辑中蒸馏出最小实现：不 import dexechain / embodichain，只依赖本地 W1 URDF、`torch` 和 `pytorch_kinematics`。在 UniVis 中这两个运行时依赖作为可选 extra 提供，例如 `uv sync --extra w1-fk`。

参考实现：

- `/home/dex/app/embodichain/dexechain/agents/dexforce_vla/models/losses/forward_kinematics_loss.py`
- `/home/dex/app/embodichain/dexechain/lab/gym/utils/gym_utils.py`

`ForwardKinematicsLoss` 中的关键逻辑：

1. 调用 `get_pk_serial_chain_from_robot_type(robot_type, has_waist=has_waist)` 获取左右臂 `pytorch_kinematics.SerialChain`。
2. 根据 `has_waist` 决定 FK 输入是 `arm qpos` 还是 `waist qpos + arm qpos`。
3. 调用 `serial_chain.forward_kinematics(qpos, end_only=True).get_matrix()`。
4. 从 4x4 matrix 中取：
   - `xyz = matrix[:3, 3]`
   - `rot6d = concat(matrix[:3, 0], matrix[:3, 1])`

建议类：

```python
class W1ForwardKinematics:
    def __init__(self, config: DexforceW1TeleopConfig) -> None:
        ...

    def compute_dual_arm_eef(self, qpos: np.ndarray) -> W1FKResult:
        ...
```

建议模型：

```python
class W1ArmFKResult(BaseModel):
    xyz: list[float]
    rot6d: list[float]


class W1FKResult(BaseModel):
    left: W1ArmFKResult
    right: W1ArmFKResult
```

说明：

- 输入 `qpos` 应是单帧全量 qpos，而不是已切好的 arm qpos。
- `W1ForwardKinematics` 根据 config 中的 `waist_joint_names`、`left_arm_joint_names`、`right_arm_joint_names` 从全量 qpos 中组装 FK 输入。
- 第一版只实现 FK，不实现 IK。
- FK 依赖 dexechain / pytorch_kinematics 时，依赖应隔离在该 format 内部，避免 UniVis 核心模块直接 import dexechain。
- 第一版实际实现应避免依赖 dexechain，只允许依赖 `torch`、`pytorch_kinematics` 和配置里的本地 URDF 路径。

## Dexforce W1 Adapter Design

建议新增格式目录：

- `univis/formats/dexforce_w1_teleop/__init__.py`
- `univis/formats/dexforce_w1_teleop/adapter.py`
- `univis/formats/dexforce_w1_teleop/manifest.py`
- `univis/formats/dexforce_w1_teleop/sync.py`
- `univis/formats/dexforce_w1_teleop/fk.py`
- `univis/formats/dexforce_w1_teleop/settings.py`
- `univis/formats/dexforce_w1_teleop/config/default.yaml`

建议 adapter 名称：

- class: `DexforceW1TeleopAdapter`
- label: `Dexforce W1 Teleop`
- alias: `W1Teleop`

### Adapter Responsibilities

`DexforceW1TeleopAdapter` 应负责：

1. 扫描 episode 目录。
2. 读取 `metadata.jsonl`。
3. 读取 `pose_record_*.json`。
4. 按图像时间戳对 qpos 做插值。
5. 保留插值后的全量 qpos。
6. 从全量 qpos 中读取 gripper 值。
7. 调用 `W1ForwardKinematics.compute_dual_arm_eef()` 将全量 qpos 转为左右臂 EEF pose。
8. 构造 `PolicyEpisode`。
9. 提供 `get_image_frame()`，直接从原始图像路径返回图像。
10. 支持读取/写回语言标注，具体写回位置需要后续确认。

Adapter 不应负责：

- 实现通用 FK/IK 抽象。
- 实现 IK。
- 写 HDF5。
- 执行 reachability 筛选。
- 执行 DTW/smooth 质量分析。

## Config Sketch

```yaml
format:
  name: dexforce_w1_teleop
  label: Dexforce W1 Teleop

source:
  episode_pattern: "*"
  metadata_file: metadata.jsonl
  qpos_pattern: "pose_record_*.json"
  instruction_field: language_prompt

cameras:
  head_left:
    key: camera_head_left
    label: Head Left
    camera_type: head
    place: left
    path: head/left
    suffixes: [".jpg", ".jpeg", ".png"]
  head_right:
    key: camera_head_right
    label: Head Right
    camera_type: head
    place: right
    path: head/right
    suffixes: [".jpg", ".jpeg", ".png"]
  hand_left:
    key: camera_hand_left
    label: Hand Left
    camera_type: hand
    place: left
    path: hand/left
    suffixes: [".jpg", ".jpeg", ".png"]
  hand_right:
    key: camera_hand_right
    label: Hand Right
    camera_type: hand
    place: right
    path: hand/right
    suffixes: [".jpg", ".jpeg", ".png"]

qpos:
  joint_order:
    - ANKLE
    - KNEE
    - BUTTOCK
    - WAIST
    - NECK1
    - NECK2
    - LEFT_J1
    - LEFT_J2
    - LEFT_J3
    - LEFT_J4
    - LEFT_J5
    - LEFT_J6
    - LEFT_J7
    - LEFT_GRIPPER
    - RIGHT_J1
    - RIGHT_J2
    - RIGHT_J3
    - RIGHT_J4
    - RIGHT_J5
    - RIGHT_J6
    - RIGHT_J7
    - RIGHT_GRIPPER
    - LEFT_HAND_THUMB1
    - LEFT_HAND_THUMB2
    - LEFT_HAND_INDEX
    - LEFT_HAND_MIDDLE
    - LEFT_HAND_RING
    - LEFT_HAND_PINKY
    - RIGHT_HAND_THUMB1
    - RIGHT_HAND_THUMB2
    - RIGHT_HAND_INDEX
    - RIGHT_HAND_MIDDLE
    - RIGHT_HAND_RING
    - RIGHT_HAND_PINKY
  body:
    waist_joint_names: [WAIST]
    head_joint_names: [NECK1, NECK2]
  arms:
    left:
      joint_names: [LEFT_J1, LEFT_J2, LEFT_J3, LEFT_J4, LEFT_J5, LEFT_J6, LEFT_J7]
      gripper_name: LEFT_GRIPPER
    right:
      joint_names: [RIGHT_J1, RIGHT_J2, RIGHT_J3, RIGHT_J4, RIGHT_J5, RIGHT_J6, RIGHT_J7]
      gripper_name: RIGHT_GRIPPER

sync:
  reference_camera: head_left
  camera_tolerance_ms: 30.0
  qpos_tolerance_ms: 30.0
  min_frames: 45

kinematics:
  fk_impl: dexechain_pk_serial_chain
  robot: W1
  robot_type: DexForceW1
  has_waist: true
  fail_policy: error

processing:
  gripper_normalization:
    left:
      min: 0.0
      max: 1.0
    right:
      min: 0.0
      max: 1.0
```

## First Implementation Plan

### Phase A: W1 FK Helper

1. 新增 `formats/dexforce_w1_teleop/fk.py`。
2. 定义 `W1ForwardKinematics` 和 `W1FKResult`。
3. 输入单帧全量 qpos，输出左右臂 `xyz + rot6d`。
4. 第一版按 `ForwardKinematicsLoss` 的方式调用 `pytorch_kinematics.SerialChain.forward_kinematics()`。
5. 不实现 IK，不新增全局 `univis.kinematics` 抽象。

### Phase B: Dexforce W1 Adapter Skeleton

1. 新增 `formats/dexforce_w1_teleop` 目录。
2. 实现 metadata/qpos 扫描、自然排序、时间戳插值。
3. 同步结果保留全量 qpos。
4. 使用 W1 FK helper 构造 `PolicyEpisode`。
5. 实现 `list_metadata()`、`load_episode()`、`get_image_frame()`。
6. 注册到 `load_format_components()`。

### Phase C: Real Data Validation

1. 增加一条真实遥操 episode 的 smoke test。
2. 验证全量 qpos 插值结果与旧 `tele2hdf5` 对齐方式一致。
3. 验证 FK 输出 `xyz + rot6d` 和 dexechain 训练链路中 FK 结果一致。
4. 验证 GUI 可视化、DTW 和 smooth 可以直接消费该 adapter 输出。

### Phase D: IK Future Work

IK 暂不实现。后续 reachability 真正需要 W1 全身 IK 时，再基于 W1 的实际 IK 能力单独设计，而不是沿用本阶段被移除的通用 FK/IK 抽象。

## Acceptance Criteria

第一阶段验收：

- adapter 设计明确读取全量 qpos，但输出统一 `PolicyEpisode`。
- W1 FK 是 `formats/dexforce_w1_teleop` 内部实现，不引入全局 kinematics 抽象。
- 第一版不实现 IK。
- dexechain / pytorch_kinematics 依赖只允许出现在 W1 format 内部，不扩散到 UniVis 核心模块。

第二阶段验收：

- 前端 input format 下拉框能看到 `Dexforce W1 Teleop`。
- 选择包含遥操 episode 的目录后能列出 episode。
- 能打开 episode 并看到图像和由 W1 FK 计算出的双臂 EEF 轨迹。
- DTW 和 smooth 能直接消费该 adapter 输出。
