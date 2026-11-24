# Keyremap 用例汇总

> 维护人：Sophy H400818 ｜ 创建日期：2026-09-01
> 覆盖 Settings → Honeywell Settings → Keyremap 的按键重映射自动化用例。

## 一、用例清单

| # | Jira ID | 用例文件 | 源键 | 目标 | 说明 |
|---|---------|----------|------|------|------|
| 1 | ANDROIDCN-34839 | [case/smoking/test_L0_keyremap_ANDROIDCN_34839.py](../smoking/test_L0_keyremap_ANDROIDCN_34839.py) | BACK | HOME | L0 冒烟：新增映射 → 触发 → Clear All → 验证恢复 |
| 2 | ANDROIDCN-34830 | [test_L2_virtual_back_key_remap_home_ANDROIDCN_34830.py](test_L2_virtual_back_key_remap_home_ANDROIDCN_34830.py) | BACK | HOME | 按 Back 回到桌面 |
| 3 | ANDROIDCN-35652 | [test_L2_virtual_bac_kkey_remap_app_switch_ANDROIDCN-35652.py](test_L2_virtual_bac_kkey_remap_app_switch_ANDROIDCN-35652.py) | BACK | APP_SWITCH | 按 Back 打开最近任务 |
| 4 | ANDROIDCN-34515 | [test_L2_virtual_back_key_remap_menu_ANDROIDCN_34515.py](test_L2_virtual_back_key_remap_menu_ANDROIDCN_34515.py) | BACK | MENU | 桌面按 Back 弹出 Launcher 菜单 |
| 5 | ANDROIDCN-33202 | [test_L2_virtual_back_key_remap_volume_mute_ANDROIDCN_33202.py](test_L2_virtual_back_key_remap_volume_mute_ANDROIDCN_33202.py) | BACK | VOLUME_MUTE | 按 Back 静音 |
| 6 | ANDROIDCN-35751 | [test_L2_virtual_back_key_remap_text_ANDROIDCN_35751.py](test_L2_virtual_back_key_remap_text_ANDROIDCN_35751.py) | BACK | TEXT | 5 步：TEST / Ctrl+A / A+VOLUME_UP |
| 7 | ANDROIDCN-33264 | [test_L2_virtual_home_key_remap_app_switch_ANDROIDCN_33264.py](test_L2_virtual_home_key_remap_app_switch_ANDROIDCN_33264.py) | HOME | APP_SWITCH | 按 Home 打开最近任务 |
| 8 | ANDROIDCN-34181 | [test_L2_virtual_home_key_remap_menu_ANDROIDCN_34181.py](test_L2_virtual_home_key_remap_menu_ANDROIDCN_34181.py) | HOME | MENU | 桌面按 Home 弹出 Launcher 菜单 |
| 9 | ANDROIDCN-35491 | [test_L2_virtual_home_key_remap_volume_mute_ANDROIDCN_35491.py](test_L2_virtual_home_key_remap_volume_mute_ANDROIDCN_35491.py) | HOME | VOLUME_MUTE | 按 Home 静音 |
| 10 | ANDROIDCN-36228 | [test_L2_virtual_home_key_remap_text_ANDROIDCN_36228.py](test_L2_virtual_home_key_remap_text_ANDROIDCN_36228.py) | HOME | TEXT | 5 步：TEST / Ctrl+A / A+VOLUME_UP |
| 11 | ANDROIDCN-33165 | [test_L2_virtual_home_key_remap_apps_ANDROIDCN_33165.py](test_L2_virtual_home_key_remap_apps_ANDROIDCN_33165.py) | HOME | APPS | 安装 APK → APPS 页选中该 app → 按 Home 拉起它 |
| 11 | ANDROIDCN-35822 | [test_L2_virtual_appswitch_keyremap_home_ANDROIDCN_35822.py](test_L2_virtual_appswitch_keyremap_home_ANDROIDCN_35822.py) | APP_SWITCH | HOME | 按 Overview 回到桌面 |
| 12 | ANDROIDCN-35284 | [test_L2_virtual_appswitch_key_remap_menu_ANDROIDCN_35284.py](test_L2_virtual_appswitch_key_remap_menu_ANDROIDCN_35284.py) | APP_SWITCH | MENU | 桌面按 Overview 弹出 Launcher 菜单 |
| 13 | ANDROIDCN-35903 | [test_L2_virtual_appswitch_key_remap_volume_mute_ANDROIDCN_35903.py](test_L2_virtual_appswitch_key_remap_volume_mute_ANDROIDCN_35903.py) | APP_SWITCH | VOLUME_MUTE | 按 Overview 静音 |
| 14 | ANDROIDCN-35035 | [test_L2_virtual_appswitch_key_remap_text_ANDROIDCN_35035.py](test_L2_virtual_appswitch_key_remap_text_ANDROIDCN_35035.py) | APP_SWITCH | TEXT | 5 步：TEST / Ctrl+A / A+VOLUME_UP |

## 二、通用测试流程

1. `keyremap_open_page` 打开 Settings → Honeywell Settings → Keyremap（force-stop + root kill PID 保证页面刷新）
2. `keyremap_tap_add_button` 清空旧映射并点击 `+`
3. `keyremap_dialog_is_open` 确认 "Please press the key to be mapped" 弹窗
4. `keyremap_click_virtual_back / _home / _appswitch` 点击虚拟按键（替代物理扫描键）
5. `keyremap_tap_ok_button` → `keyremap_tap_text` 在目标列表中选择映射目标
6. 回桌面后用 `keyremap_tap_navbar_*` 点击导航栏触发映射（**adb keyevent 会绕过 Keyremap 拦截，必须点导航栏**）
7. 断言目标行为，`tearDown` 中 `keyremap_clear_all` 清理映射

## 三、TEXT 类用例的 5 个 Step

| Step | 映射内容 | 验证点 |
|------|----------|--------|
| 1 | `T,E,S,T` | Keyremap 列表出现该条目 |
| 2-3 | 同上 | 桌面搜索框按键后收到 `test` |
| 4 | `CTRL_LEFT,A` | 输入 `hello` 后按键 → 再输入一个字符，内容被整体替换即证明全选 |
| 5 | `A,VOLUME_UP` | 快速连按 N 次 → 输入框出现 N 个 `a`，且音量档位上升 |

## 四、公共方法

### common/adb_common.py

| 方法 | 说明 |
|------|------|
| `keyremap_open_page` *(common_method)* | 导航到 Keyremap 页面 |
| `keyremap_click_virtual_back / _home / _appswitch` | 点击弹窗内虚拟按键（1080x2160 固定坐标） |
| `keyremap_tap_navbar_back / _home / _appswitch(serial, wait=2)` | 点击导航栏按键触发映射；按 `wm size` 等比缩放，`wait` 可调小用于快速连按 |
| `keyremap_is_on_home_screen` | 多信号判断是否已回到 Launcher |
| `keyremap_is_on_recent_apps` | 判断是否在最近任务界面（dumpsys 关键字 + Quickstep UI 兜底） |
| `keyremap_dump_recents_ui_markers` | dump hierarchy，返回仅存在于 Overview 的控件 id |
| `keyremap_is_stream_muted` | 解析 `dumpsys audio` 判断静音 |
| `keyremap_get_stream_volume_index` | 解析 `dumpsys audio` 读取音量档位 |
| `keyremap_set_stream_volume_index` | 用音量键逐步逼近目标档位（该平台 `cmd media_session volume --set` 无效） |
| `keyremap_force_stop_honeywell_settings` | 清理 Honeywell Settings |

### common/common_method.py

| 方法 | 说明 |
|------|------|
| `keyremap_find_text_center` / `keyremap_find_desc_center` | 从 hierarchy 解析控件中心坐标 |
| `keyremap_tap_text` | 滚动查找并点击文本 |
| `keyremap_tap_add_button` / `keyremap_clear_entries` / `keyremap_clear_all` | 新增/清理映射条目 |
| `keyremap_dialog_is_open` / `keyremap_tap_ok_button` | 弹窗状态与确认 |
| `keyremap_select_target` / `keyremap_select_home_target` | 选择映射目标 |
| `keyremap_is_android_menu_shown` | 判断 Launcher 菜单是否弹出 |
| `keyremap_input_text_value` | 向 `com.honeywell.keyremap2:id/et_string` 输入映射字符串 |
| `keyremap_read_edit_text` | 读取输入框内容 |
| `keyremap_is_text_selection_active` | 输入一个字符验证是否全选 |
| `get_package_name` / `get_case_config` | 读取 commands.config / allconfig.config |

## 五、配置

### common/commands.config `[package_names]`
```ini
settings=com.android.settings
keyremap=com.honeywell.keyremap2
```

### common/allconfig.config `[keyremap_text_case]`
```ini
remap_text_input=T,E,S,T
expected_text=test
select_all_input=CTRL_LEFT,A
probe_text=hello
text_and_volume_input=A,VOLUME_UP
step5_press_count=3
volume_streams=STREAM_MUSIC,STREAM_RING
volume_stream_name=STREAM_MUSIC
default_volume_index=5
```

## 六、已知坑位

- **adb keyevent 绕过 Keyremap**：`input keyevent KEYCODE_HOME/BACK` 不会被 Keyremap 服务拦截，只能用于「回到某状态」，触发映射必须点击导航栏坐标。
- **导航栏坐标**：基准 1080 宽，Back=150、Home=470、Overview=789，y 取 `screen_height - 72`，其他分辨率按宽度等比缩放。
- **音量设置**：`cmd media_session volume --stream 3 --set N` 在本平台静默失败，改用 `input keyevent 24/25` 循环逼近。
- **VOLUME_UP 需快速连按**：Step 5 中间不要插入 UI 读取/截图，用 `wait=0.2`。
- **文本选中无法直接读取**：`selected` 属性与文本选区无关，`dumpsys input_method` 的 selStart/selEnd 也不可靠，改用「再输入一个字符看是否被整体替换」的行为验证。
- **重命名用例文件后**须同步更新 `data/timer_tasks.json` 中保存任务的 `caseList` 路径，否则装载 0 条用例。
- **Quickstep 机型最近任务检测**：本机 Launcher 为 `com.android.launcher3/com.android.searchlauncher.SearchLauncher`，Overview 是 Launcher 窗口内的一层 overlay，进入最近任务后 `mCurrentFocus` / `topResumedActivity` 仍是 SearchLauncher，dumpsys 关键字全部匹配不到。改为再 dump 一次 UI hierarchy，用 Overview 独有控件判定：
  - `com.android.launcher3:id/overview_panel`
  - `com.android.launcher3:id/action_screenshot`（文本 “Screenshot”）
  - 注意 `overview_actions_view` 在桌面也存在，**不能**作为判据。

## 七、故障排查

### 7.1 截图上控件明明在，脚本却报 “xxx not found”（uiautomator 服务掉线）（CT37 找不到honeywell settings选项）

**现象**（2026-09-02 于 CT37 / 24330X02D6 复现）

Step 1 报 `Could not navigate to Keyremap page`，但 `step1_nav_failed_*.png` 截图里 “Honeywell Settings” 清清楚楚显示在屏幕上。日志里连续刷：

```
[Hier] dump_hierarchy failed: RPCUnknownError: ('Unknown RPC error: -32001 java.lang.NullPointerException', ...)
[Nav] 'Honeywell Settings' not found
```

**根因**

`d.dump_hierarchy()` 抛出：

```
java.lang.NullPointerException: Attempt to read from field
'int android.accessibilityservice.AccessibilityServiceInfo.flags' on a null object reference
in method 'void androidx.test.uiautomator.UiDevice.setCompressedLayoutHeirarchy(boolean)'
```

即 `com.github.uiautomator` 进程还活着，但它持有的 UiAutomation / AccessibilityService 连接已经断开
（`adb shell settings get secure enabled_accessibility_services` 返回 `null`）。
截图走的是 `screencap`，不依赖无障碍服务，所以图是好的；而所有基于 hierarchy 的控件定位全部失效。

**定位方法**

```powershell
# 1. 确认 dump 是否真的挂了
python -c "import uiautomator2 as u2; d=u2.connect('<serial>'); print(len(d.dump_hierarchy()))"

# 2. 看无障碍服务是否为 null
adb -s <serial> shell settings get secure enabled_accessibility_services

# 3. 看 uiautomator 进程是否残留
adb -s <serial> shell "ps -A | grep -i uiautomat"
```

**解决办法**（注意：只调 `stop_uiautomator()` + `start_uiautomator()` 无效，必须先把残留进程杀干净）

```powershell
adb -s <serial> shell am force-stop com.github.uiautomator
adb -s <serial> shell am force-stop com.github.uiautomator.test
adb -s <serial> shell "pkill -f uiautomator"
```

然后重新拉起并校验：

```powershell
python -c "import uiautomator2 as u2, time; d=u2.connect('<serial>'); d.start_uiautomator(); time.sleep(6); print('len:', len(d.dump_hierarchy()))"
```

`len` 能正常打印出数字（如 34819）即恢复，随后用例即可跑通。

**经验**：以后遇到「截图上控件在、脚本找不到」，先怀疑 uiautomator 服务掉线，不要一上来就改定位逻辑。

**复现记录**（2026-09-11 于 CT37 / 24330X02D6 再次复现，跑 `test_L2_virtual_home_key_remap_middle_scan_ANDROIDCN_35006` 时触发）：`enabled_accessibility_services` 查询结果为 `null`，`ps -A | grep uiautomat` 可见 `com.github.uiautomator` 残留进程。按上述解决办法清理并重启后，`dump_hierarchy()` 恢复正常（长度 34801），用例可继续执行。说明此问题非一次性，同一台设备会反复出现，排查时可直接按本节步骤处理。

### 7.2 输入框内容读成空字符串（读取方法选错，非功能问题）

**现象**（2026-09-02 于 ANDROIDCN-35035 复现）

Step 4 报：

```
Field content after typing one character: ''
AssertionError: Step 4 Failed: the search field content was not selected ... (content='', expected a single character)
```

Step 5 报：

```
Field content after 3 presses: ''
AssertionError: Step 5 Failed: after 3 press(es) the field should contain 3 'a' character(s), got ''
```

但截图里搜索框明明分别是 `Z` 和 `aaa`，即 **映射功能本身是正常的**。

**根因**

`scan_get_input_field_text` 用 `device(focused=True)` 且**不限定 className**，一命中就直接 `return`：

```python
focused = device(focused=True)
if focused.exists(timeout=0.2):
    return (focused.get_text() or "").strip()   # 命中空容器 → 返回 ""，不再走 EditText 兜底
```

Google 搜索框的焦点节点是一层空文本的外层容器（Step 5 还叠了音量面板 overlay），
于是拿到空串就直接返回，既不会 fallback 到 `android.widget.EditText`，也没有重试。

对比 Step 3 用的 `keyremap_read_edit_text` 就正常：它**限定 `android.widget.EditText`，并轮询到非空才返回**。

**解决办法**

TEXT 类用例中所有「读输入框内容」一律用 `keyremap_read_edit_text(device)`，不要用 `scan_get_input_field_text`：

- `common/common_method.py` → `keyremap_is_text_selection_active`：改用 `keyremap_read_edit_text`，
  `scan_get_input_field_text` 仅作兜底，且比较忽略大小写。
- `test_L2_virtual_appswitch_key_remap_text_ANDROIDCN_35035.py` Step 5：同样换成 `keyremap_read_edit_text`。

修复后实测：Step 4 读到 `'Z'`（全选生效），Step 5 读到 `'aaa'` 且 STREAM_MUSIC 5 → 8，5 个 Step 全通过。

**经验**：断言失败前先看截图。截图与断言不一致时，问题一般在读取/定位方法，而不是被测功能。

### 7.3 tearDown 静默跳过清理，映射残留（Overview overlay 吃掉滑动）

**现象**（2026-09-02 于 ANDROIDCN-33264 复现）

用例 3 个 Step 全部通过、结果是 OK，但日志末尾多一行：

```
[L2_Keyremap] All steps passed ✓
  [Nav] Killed com.honeywell.keyremap2 PID=4083
  [Nav] 'Honeywell Settings' not found      ← 异常点
[TearDown] Completed: ...
```

实测设备上仍残留 `HOME → APP_SWITCH` 映射，下一条用例会带着脏状态跑。

**根因**

tearDown 进入时设备停在 Overview（最近任务）界面。`keyremap_open_page` 直接 `am start` 拉起 Settings，
`dumpsys` 已经报 `mCurrentFocus=com.android.settings`，但 **Quickstep 的 Overview overlay 窗口仍压在最上层，
吃掉所有触摸事件**，Settings 列表根本滚不动。逐次滑动探针：

| swipe | 抓到的文本 | 实际情况 |
|---|---|---|
| 0-2 | Settings 顶部条目 + **`CLEAR ALL`** | `CLEAR ALL` 是 Overview 的按钮，overlay 还在，列表一格没滚 |
| 3 | Phone / Contacts / Gmail | 滑动把 Overview 划掉，落到桌面 |
| 4-6 | ATX / Calculator / Chrome… | 继续滑，打开了应用抽屉 |

6 次滑动全打在别的界面上，自然找不到 "Honeywell Settings"。
而 tearDown 写成 `if keyremap_open_page(...): keyremap_clear_all(...)`，返回 False 就直接跳过清理，
**不抛异常、不影响用例结果**，所以是个静默失败。

**解决办法**

在 `common/common_method.py` 的 `keyremap_open_page` 里，启动 Settings 前先发一次 HOME 键消掉 overlay
（adb keyevent 不被 Keyremap 拦截，见第六节，安全）：

```python
# Dismiss any Quickstep Overview overlay first: it stays on top of the freshly started Settings
# window and swallows the scroll gestures, so the entry list would never scroll.
run_adb_cmd(serial, "shell input keyevent KEYCODE_HOME", log_print=False)
time.sleep(1)
run_adb_cmd(serial, f"shell am force-stop {settings_package}", log_print=False)
```

验证：Overview 场景下 `keyremap_open_page` 由 `False` → `True`；重跑用例 tearDown 不再报 not found，
Keyremap 列表回到只剩标题 `['Keyremap']`。该方法被所有 keyremap 用例共用，
`APP_SWITCH → *` 那几条（Step 3 同样停在 Overview）一并修好。

**经验**：`if xxx(): cleanup()` 形式的 tearDown 会掩盖清理失败。用例 PASS 时也要扫一眼 tearDown 日志，
或改成清理失败时显式打印告警。

### 7.4 APP 类型映射条目无文字，按 label 校验必失败

**现象**（2026-09-02 于 ANDROIDCN-33165 复现）

Step 2 保存映射后报：

```
AssertionError: Step 2 Failed: 'StressTest' not shown in Keyremap list after saving
```

但截图里映射**已经存上了**，Keyremap 列表显示 `HOME → [app 图标]`。

**根因**

Keyremap 列表对不同目标类型的渲染方式不一样：

| 目标类型 | 列表渲染 | 能否按文字定位 |
|---|---|---|
| KEYS（HOME / MENU / APP_SWITCH…） | 文字 | ✅ |
| TEXT | 文字（`User Text`） | ✅ |
| **APPS** | **仅 app 图标，无 text、无 content-desc** | ❌ |

所以 `keyremap_find_text_center(d, "StressTest")` 永远返回 None。

**解决办法**

APP 类型用例不要校验目标 label，改为：

1. 保存后只校验**源键行**存在（`keyremap_find_text_center(d, "HOME", contains=False)`）；
2. 映射是否正确，交给后续 Step「按键后目标 app 是否被拉起」来断言
   （`keyremap_wait_app_foreground(serial, package)` 轮询 dumpsys window/activity）。

```python
# An APP target is rendered as an icon only, so the saved row is confirmed by its source key.
if keyremap_find_text_center(d, "HOME", contains=False) is None:
    self.fail("Step 2 Failed: 'HOME' entry not shown in Keyremap list after saving")
```

**配套约定**：app 的 label 不要手写猜测，用 aapt 读准确值再写进 `allconfig.config`：

```powershell
& "$env:LOCALAPPDATA\Android\Sdk\build-tools\36.0.0\aapt.exe" dump badging <apk> |
  Select-String -Pattern "^package|application-label:|launchable-activity"
```

本例结果：`com.honeywell.stresstest` / label `StressTest` / `.MainActivity`。

### 7.5 多机 / 换机注意

- `get_device_serial()` 未设 `ANDROID_SERIAL` 时取 `adb devices` 第一台，换机后请先 `adb devices` 确认目标机。
- CT37（1080x2136）与 CT47（1080x2160）分辨率不同：`keyremap_tap_navbar_*`、`keyremap_click_virtual_back /
  _home / _appswitch`、`keyremap_swipe_up`、`keyremap_clear_entries`、`keyremap_tap_add_button` 均已按
  `wm size` 等比缩放（见 7.7），换分辨率机型（含 480x800 等小屏设备）也是安全的。

### 7.6 UI Automator Viewer 报错 `SyncException: Remote object doesn't exist!`

**现象**（2026-09-08 于 CT47 / 26035B5F7D 复现）

打开 UI Automator Viewer 点截图/dump 按钮，弹窗：

```
Error obtaining UI hierarchy
Error while obtaining UI hierarchy XML file: com.android.ddmlib.SyncException: Remote object doesn't exist!
```

**根因**

设备上跑着本仓库自动化用例依赖的 `uiautomator2` 守护服务：`atx-agent`（常驻进程）会持续保活
`com.github.uiautomator`，二者共同占用 Android 的 `UiAutomation` / 无障碍服务连接，
该连接**同一时刻只能被一个进程持有**。UI Automator Viewer 内部走的是旧版
`adb shell uiautomator dump`，抢不到这个连接，进程被系统直接 `Killed`，
dump 文件根本没生成，Viewer 用 ddmlib 去 pull 一个不存在的文件，于是报
`Remote object doesn't exist!`。

只 `am force-stop com.github.uiautomator` 无效：`atx-agent` 会立刻把它重新拉起来，
通道马上又被占用。

**定位方法**

```powershell
adb devices -l
adb shell "ps -A | grep -iE 'uiautomator|atx'"
adb shell "uiautomator dump /sdcard/window_dump.xml 2>&1"
adb shell ls -la /sdcard/window_dump.xml
```

`ps` 里能看到 `atx-agent`（shell 用户）和 `com.github.uiautomator`（u0_axxx）同时在跑；
`uiautomator dump` 直接打印 `Killed`，且目标文件时间戳不更新，即可确认是这个问题。

**解决办法**：连 `com.github.uiautomator` 一起把 `atx-agent` 也杀掉，才能真正释放通道：

```powershell
adb shell "ps -A | grep atx-agent"          # 查 atx-agent 的 PID
adb shell am force-stop com.github.uiautomator
adb shell kill -9 <atx-agent的PID>          # 例如 kill -9 6011
```

之后立即重试 `uiautomator dump` / UI Automator Viewer 即可成功。

**注意**：杀掉 `atx-agent` 后，本仓库所有依赖 `u2.connect(serial)` 的 Python 用例会暂时连不上；
下次任何脚本调用 `u2.connect()` 时，`uiautomator2` 库会自动检测并重新拉起 `atx-agent`，一般几秒内自愈，
无需手动执行 `python -m uiautomator2 init`。

**经验**：只要 `atx-agent` 还活着，它就会不断把 `com.github.uiautomator` 抢回来；
想临时用 UI Automator Viewer 排查页面，必须把 `atx-agent` 一并杀掉，而不仅仅是它拉起的 app 进程。
更推荐的做法是排查页面时直接用 Python 里的 `device.dump_hierarchy()` 或本仓库的
`keyremap_find_text_center`，完全绕开这个连接抢占问题。

### 7.7 小分辨率设备（如 480x800）滑动/点击无效（坐标越界被系统丢弃）

**现象**（2026-09-09 于 CK67 / 25008E0021 复现）

同一份 Keyremap 用例在 CT47（1080x2160）上跑得好好的，换到分辨率只有 480x800 的机型后，
Settings 页面滑不动、Keyremap 弹窗里的虚拟按键点不中，但页面本身是正常的、也没有锁屏。

**根因**

`common_method.py` / `adb_common.py` 里不少 keyremap 相关函数用的是**写死的绝对像素坐标**，
这些坐标是按 1080x2160 基准设备量出来的（如 `input tap 828 1203`、`input swipe 540 1400 540 400`）。
在 480x800 的设备上，这些坐标的 x（如 828、1004）已经**超出屏幕宽度（0~479）**，
触摸事件的起止点落在屏幕范围之外，Android 输入子系统会直接丢弃这次手势/点击，
而不是报错——所以看起来像是"滑不动""点不中"，而不是崩溃或异常。

**定位方法**

```powershell
adb -s <serial> shell wm size                      # 确认实际分辨率，例如 Physical size: 480x800
adb -s <serial> shell uiautomator dump /sdcard/before.xml
adb -s <serial> shell input swipe 500 1600 500 400 300
adb -s <serial> shell uiautomator dump /sdcard/after.xml
adb -s <serial> shell md5sum /sdcard/before.xml /sdcard/after.xml   # 相同 md5 = 滑动没有任何效果
```

**解决办法**：涉及绝对坐标的 keyremap 函数统一改为「读取 `wm size`，按 1080x2160 基准等比缩放」，
在 1080x2160 设备上换算结果与原坐标完全一致，不影响现有机型：

- `common/adb_common.py`：`keyremap_swipe_up`、`keyremap_click_virtual_appswitch`、
  `keyremap_click_virtual_home`、`keyremap_tap_navbar_home/appswitch/back`（连 Y 轴的
  `screen_height - 72` 固定像素偏移也一并改成按比例换算）。
- `common/common_method.py`：`keyremap_clear_entries`（菜单图标 + ALL SELECT/DELETE/OK 兜底坐标）、
  `keyremap_tap_add_button`（"+" 按钮坐标）。

`keyremap_click_virtual_back` 此前已经是按比例缩放的写法，作为参考模板复用到了以上函数里。

**经验**：任何 `input tap`/`input swipe` 硬编码坐标，上线前都要问一句「这串数字是基于多大的屏幕量出来的」；
凡是要跨机型复用的自动化代码，一律先 `wm size` 拿到实际分辨率再按比例换算，不要假设所有设备是同一分辨率。


