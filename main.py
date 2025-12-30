import flet as ft
import json
import os
import threading
from datetime import datetime
from script import Connectivity, export, server

# ---------- 表格行 ----------
def proxy_row(item, header=False, on_click_callback=None):
    def cell(text, flex=1, bold=False, color=None):
        return ft.Container(
            expand=flex,
            padding=8,
            content=ft.Text(
                text,
                size=11,
                weight=ft.FontWeight.BOLD if bold else ft.FontWeight.NORMAL,
                color=color if color else ("#E0E0E0" if not header else ft.Colors.WHITE),
                no_wrap=True,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
        )

    status_color = {
        "可用": "#66BB6A",
        "检测中": "#FFA726",
        "不可用": "#EF5350",
    }.get(item.get("status", ""), None)

    row_container = ft.Container(
        bgcolor="#4A2C6D" if header else "#2A1A3D",
        border=ft.border.only(bottom=ft.BorderSide(1, "#3D2557")),
        content=ft.Row(
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                cell(item.get("status", ""), 1, header, status_color),
                cell(str(item.get("score", "")), 1, header),
                cell(item.get("anonymity", ""), 1, header),
                cell(item.get("protocol", ""), 1, header),
                cell(item.get("address", ""), 2, header),
                cell(item.get("latency", ""), 1, header),
                cell(item.get("speed", ""), 1, header),
                cell(item.get("country", ""), 1, header),
                cell(item.get("city", ""), 1, header),
            ],
        ),
    )
    
    # 如果不是表头，添加左键点击事件
    if not header and on_click_callback:
        def handle_click(e):
            on_click_callback(item)
        
        row_container.on_click = handle_click
        row_container.ink = True
        
        # 添加悬停效果
        def handle_hover(e):
            if e.data == "true":
                row_container.bgcolor = "#5E3A7D"
            else:
                row_container.bgcolor = "#2A1A3D"
            row_container.update()
        
        row_container.on_hover = handle_hover
    
    return row_container


def main(page: ft.Page):
    page.title = "Peanut Pod"
    page.padding = 0
    page.window.width = 900
    page.window.height = 540
    page.bgcolor = "#1A0B2E"  # 深紫色背景
    page.window.icon="./assets/favicon2.ico"

    # ---------- 数据 ----------
    data = []
    try:
        base = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(base, "assets", "pool.json"), encoding="utf-8") as f:
            data = json.load(f)
        
        # 确保每个代理都有fail_count字段
        for item in data:
            if "fail_count" not in item:
                item["fail_count"] = 0
    except Exception as e:
        print(e)

    def get_timestamp():
        """获取当前时间戳"""
        return datetime.now().strftime("%H:%M:%S")
    
    # 日志列表视图
    log_list = ft.ListView(
        expand=True,
        spacing=2,
        padding=5,
        auto_scroll=True,
    )
    
    # 添加初始日志
    log_list.controls.append(
        ft.Text(
            f"[{get_timestamp()}][系统] 准备就绪...",
            size=11,
            color=ft.Colors.WHITE,
            selectable=True,
        )
    )
    log_list.controls.append(
        ft.Text(
            f"[{get_timestamp()}][日志] 等待用户操作...",
            size=11,
            color=ft.Colors.WHITE,
            selectable=True,
        )
    )

    def append_log(msg):
        """添加日志并自动滚动到底部"""
        timestamp = get_timestamp()
        log_text = ft.Text(
            f"[{timestamp}]{msg}",
            size=11,
            color=ft.Colors.WHITE,
            selectable=True,
        )
        log_list.controls.append(log_text)
        
        # 限制日志数量，避免内存占用过大
        if len(log_list.controls) > 500:
            log_list.controls.pop(0)
        
        log_list.update()

    # ---------- 表格 ----------
    # 表头（固定）
    header_row = proxy_row(
        {
            "status": "状态",
            "score": "分数",
            "anonymity": "匿名度",
            "protocol": "协议",
            "address": "代理地址",
            "latency": "延迟",
            "speed": "速度",
            "country": "国家",
            "city": "城市",
        },
        header=True,
    )
    
    # 表格内容（可滚动）
    table_list = ft.ListView(expand=True, spacing=0, padding=0)

    # ---------- 筛选控件 ----------
    def update_filter_options():
        """更新筛选选项的数量统计"""
        # 统计国家数量
        country_counts = {}
        for item in data:
            country = item.get("country", "")
            if country:
                country_counts[country] = country_counts.get(country, 0) + 1
        
        # 统计状态数量
        status_counts = {"可用": 0, "不可用": 0}
        for item in data:
            status = item.get("status", "")
            if status in status_counts:
                status_counts[status] += 1
        
        # 更新国家下拉框
        total_count = len(data)
        country_options = [ft.dropdown.Option(f"全部国家 ({total_count})")]
        for country in sorted(country_counts.keys()):
            count = country_counts[country]
            # 使用显示文本作为 key，实际值存储在 text 中
            country_options.append(ft.dropdown.Option(f"{country} ({count})"))
        
        country_dropdown.options = country_options
        if country_dropdown.value and "(" not in country_dropdown.value:
            # 保持当前选择，但更新数量
            current = country_dropdown.value
            if current == "全部国家":
                country_dropdown.value = f"全部国家 ({total_count})"
            elif current in country_counts:
                country_dropdown.value = f"{current} ({country_counts[current]})"
        else:
            country_dropdown.value = f"全部国家 ({total_count})"
        
        # 更新状态下拉框
        status_options = [
            ft.dropdown.Option(f"全部 ({total_count})"),
            ft.dropdown.Option(f"可用 ({status_counts['可用']})"),
            ft.dropdown.Option(f"不可用 ({status_counts['不可用']})"),
        ]
        status_dropdown.options = status_options
        if status_dropdown.value and "(" not in status_dropdown.value:
            current = status_dropdown.value
            if current == "全部":
                status_dropdown.value = f"全部 ({total_count})"
            elif current in status_counts:
                status_dropdown.value = f"{current} ({status_counts[current]})"
        else:
            status_dropdown.value = f"全部 ({total_count})"
        
        # 只在控件已添加到页面时才更新
        try:
            country_dropdown.update()
            status_dropdown.update()
        except:
            pass
    
    # 初始化筛选选项
    country_dropdown = ft.Dropdown(
        width=150,
        leading_icon=ft.Icons.SEARCH,
        border=ft.InputBorder.UNDERLINE,
        enable_filter=True,
        editable=True,
        content_padding=ft.padding.symmetric(horizontal=4, vertical=2),
        text_size=13,
        color=ft.Colors.WHITE,
        value="全部国家",
        options=[ft.dropdown.Option("全部国家")],
    )

    status_dropdown = ft.Dropdown(
        width=120,
        color=ft.Colors.WHITE,
        leading_icon=ft.Icons.SEARCH,
        border=ft.InputBorder.UNDERLINE,
        content_padding=ft.padding.symmetric(horizontal=4, vertical=2),
        text_size=11,
        value="全部",
        options=[ft.dropdown.Option("全部")],
    )
    
    # 更新筛选选项（注释掉，等页面添加后再调用）
    # update_filter_options()

    good_proxy_checkbox = ft.Checkbox(label="优质代理 (<2s)", value=False, label_style=ft.TextStyle(color=ft.Colors.WHITE))

    def handle_import_result(e: ft.FilePickerResultEvent):
        nonlocal data
        if not e.files:
            return
        file_path = e.files[0].path
        proxies = []
        try:
            with open(file_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    proxies.append(line)
        except Exception as ex:
            append_log(f"[导入] 读取文件失败: {ex}")
            return
        if not proxies:
            append_log("[导入] 文件中没有有效代理")
            return

        append_log(f"[导入] 共读取 {len(proxies)} 条代理，开始异步测试...")
        
        # 重置进度条
        test_progress.value = 0
        test_progress.update()
        
        # 进度回调函数
        def on_progress(completed, total, result):
            if result:
                status = "✓" if result.get("con") == "success" else "✗"
                append_log(f"[进度] {completed}/{total} {status} {result.get('ip', '')}")
            # 更新进度条
            test_progress.value = completed / total
            test_progress.update()
            page.update()
        
        # 在后台线程中执行测试
        def test_in_background():
            nonlocal data
            results = Connectivity.test_proxies(proxies, progress_callback=on_progress)
            
            # 处理结果
            process_results(results)
        
        threading.Thread(target=test_in_background, daemon=True).start()
    
    def retest_all_proxies(e):
        """重新测试所有代理"""
        nonlocal data
        if not data:
            append_log("[重测] 没有代理可测试")
            return
        
        # 提取所有代理地址
        proxies = []
        for item in data:
            protocol = item.get("protocol", "").lower()
            address = item.get("address", "")
            if address:
                proxy = f"{protocol}://{address}"
                proxies.append(proxy)
        
        if not proxies:
            append_log("[重测] 没有有效的代理地址")
            return
        
        append_log(f"[重测] 开始重新测试 {len(proxies)} 条代理...")
        
        # 重置进度条
        test_progress.value = 0
        test_progress.update()
        
        # 进度回调函数
        def on_progress(completed, total, result):
            if result:
                status = "✓" if result.get("con") == "success" else "✗"
                append_log(f"[进度] {completed}/{total} {status} {result.get('ip', '')}")
            # 更新进度条
            test_progress.value = completed / total
            test_progress.update()
            page.update()
        
        # 在后台线程中执行测试
        def test_in_background():
            nonlocal data
            results = Connectivity.test_proxies(proxies, progress_callback=on_progress)
            process_results(results)
        
        threading.Thread(target=test_in_background, daemon=True).start()
    
    def export_to_excel(e):
        """导出代理到Excel"""
        if not data:
            append_log("[导出] 没有数据可导出")
            return
        
        try:
            append_log("[导出] 正在导出数据到Excel...")
            output_path = export.export_to_excel(data)
            append_log(f"[导出] 成功导出到: {output_path}")
        except Exception as ex:
            append_log(f"[导出] 导出失败: {ex}")
    
    def process_results(results):
        """处理测试结果并更新UI"""
        nonlocal data
        
        # 创建现有代理的映射（用于保留fail_count）
        existing_proxies = {}
        for item in data:
            key = f"{item.get('protocol', '').upper()}://{item.get('address', '')}"
            existing_proxies[key] = item.get('fail_count', 0)
        
        new_data = []
        available_count = 0
        unavailable_count = 0
        
        for item in results:
            status = "可用" if item.get("con") == "success" else "不可用"
            
            # 统计数量
            if status == "可用":
                available_count += 1
            else:
                unavailable_count += 1
            
            anonymity = item.get("Anonymity", "")
            if anonymity == "Elite":
                anonymity_display = "高匿"
            elif anonymity == "Anonymous":
                anonymity_display = "普匿"
            elif anonymity == "Transparent":
                anonymity_display = "透明"
            else:
                anonymity_display = ""
            protocol_raw = item.get("Agreement", "")
            protocol_display = protocol_raw.upper()
            address = item.get("ip", "")
            latency_ms = item.get("ms", 0.0)
            latency_str = f"{latency_ms:.1f}ms" if latency_ms else ""
            speed_mbps = item.get("mbps", 0.0)
            speed_mb_s = speed_mbps / 8.0 if speed_mbps else 0.0
            speed_str = f"{speed_mb_s:.1f} MB/s" if speed_mb_s else ""
            
            # 获取或初始化fail_count
            proxy_key = f"{protocol_display}://{address}"
            fail_count = existing_proxies.get(proxy_key, 0)
            
            # 更新fail_count
            if status == "可用":
                fail_count = 0  # 可用时重置为0
            else:
                fail_count += 1  # 不可用时+1
            
            # 如果fail_count >= 5，跳过该代理（删除）
            if fail_count >= 5:
                append_log(f"[清理] 删除失败次数过多的代理: {address} (失败{fail_count}次)")
                continue
            
            new_data.append(
                {
                    "status": status,
                    "score": item.get("Score", 0.0),
                    "anonymity": anonymity_display,
                    "protocol": protocol_display,
                    "address": address,
                    "latency": latency_str,
                    "speed": speed_str,
                    "country": item.get("country", ""),
                    "city": item.get("city", ""),
                    "fail_count": fail_count,
                }
            )
        
        # 按分数从高到低排序
        data = sorted(new_data, key=lambda x: x.get("score", 0), reverse=True)
        
        # 更新筛选选项的数量
        update_filter_options()
        
        base = os.path.dirname(os.path.abspath(__file__))
        try:
            with open(os.path.join(base, "assets", "pool.json"), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            append_log(f"[完成] 已完成测试 {len(data)} 条代理")
            append_log(f"[统计] 当前可用代理 {available_count} 个，不可用代理 {unavailable_count} 个")
        except Exception as ex:
            append_log(f"[导入] 写入 pool.json 失败: {ex}")
        
        refresh_table()
        page.update()

    file_picker = ft.FilePicker(on_result=handle_import_result)
    page.overlay.append(file_picker)
    
    # ---------- 获取公网IP ----------
    # 公网IP变量
    public_ip_text = ft.Text("获取中...", size=9, color="#B39DDB")
    
    def fetch_public_ip():
        try:
            import subprocess
            result = subprocess.run(
                ["curl", "-s", "ifconfig.me"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                ip = result.stdout.strip()
                public_ip_text.value = ip
                append_log(f"[系统] 获取公网IP: {ip}")
            else:
                public_ip_text.value = "获取失败"
                append_log("[系统] 获取公网IP失败")
        except Exception as e:
            public_ip_text.value = "获取失败"
            append_log(f"[系统] 获取公网IP异常: {e}")
        public_ip_text.update()
    
    def refresh_public_ip(e):
        public_ip_text.value = "获取中..."
        public_ip_text.update()
        append_log("[系统] 正在重新获取公网IP...")
        threading.Thread(target=fetch_public_ip, daemon=True).start()
    
    # 在后台线程获取公网IP
    threading.Thread(target=fetch_public_ip, daemon=True).start()
    
    # ---------- 更多操作菜单 ----------
    more_menu = ft.PopupMenuButton(
        content=ft.Container(
            content=ft.Text("更多操作", size=13, color=ft.Colors.WHITE),
            padding=ft.padding.symmetric(horizontal=22, vertical=7),
            bgcolor=ft.Colors.GREEN,
            border_radius=5,
        ),
        items=[
            ft.PopupMenuItem(
                text="重新测试",
                icon=ft.Icons.REFRESH,
                on_click=retest_all_proxies,
            ),
            ft.PopupMenuItem(
                text="导出代理",
                icon=ft.Icons.DOWNLOAD,
                on_click=export_to_excel,
            ),
            ft.PopupMenuItem(
                text="获取公网IP",
                icon=ft.Icons.PUBLIC,
                on_click=refresh_public_ip,
            ),
        ],
        menu_position=ft.PopupMenuPosition.UNDER,
    )

    # ---------- 筛选逻辑 ----------
    def on_proxy_selected(proxy_item):
        """当左键点击选择代理时的回调"""
        address = proxy_item.get("address", "")
        protocol = proxy_item.get("protocol", "socks5").lower()
        
        # 检查哪个代理服务器被选中
        if proxy_server_1_selected["value"]:
            proxy_server_1_ip.value = address
            proxy_server_1_ip.update()
            proxy_server_1_selected["value"] = False
            
            # 恢复节点背景颜色
            if proxy_server_1_selected["container"]:
                proxy_server_1_selected["container"].border = ft.border.all(2, ft.Colors.GREY_400)
                proxy_server_1_selected["container"].bgcolor = ft.Colors.BLACK38
                proxy_server_1_selected["container"].update()
            
            append_log(f"[设置] 代理服务器 -> {address}")
            
            # 如果代理服务器正在运行，动态切换上游代理
            if proxy_running["value"]:
                append_log(f"[切换] 正在切换上游代理...")
                server.switch_upstream_proxy(address, protocol)
                append_log(f"[切换] 上游代理已切换到 {address}")
            
        elif proxy_server_2_selected["value"]:
            proxy_server_2_ip.value = address
            proxy_server_2_ip.update()
            proxy_server_2_selected["value"] = False
            
            # 恢复节点背景颜色
            if proxy_server_2_selected["container"]:
                proxy_server_2_selected["container"].border = ft.border.all(2, ft.Colors.GREY_400)
                proxy_server_2_selected["container"].bgcolor = ft.Colors.BLACK38
                proxy_server_2_selected["container"].update()
            
            append_log(f"[设置] 代理服务器(1) -> {address}")
            
        elif proxy_server_3_selected["value"]:
            proxy_server_3_ip.value = address
            proxy_server_3_ip.update()
            proxy_server_3_selected["value"] = False
            
            # 恢复节点背景颜色
            if proxy_server_3_selected["container"]:
                proxy_server_3_selected["container"].border = ft.border.all(2, ft.Colors.GREY_400)
                proxy_server_3_selected["container"].bgcolor = ft.Colors.BLACK38
                proxy_server_3_selected["container"].update()
            
            append_log(f"[设置] 代理服务器(2) -> {address}")
        else:
            append_log("[提示] 请先点击左侧代理服务器节点进行选中")
    
    def refresh_table(e=None):
        table_list.controls.clear()

        # 提取实际的筛选值（去掉数量）
        country_value = country_dropdown.value
        if country_value and " (" in country_value:
            country_value = country_value.split(" (")[0]
        
        status_value = status_dropdown.value
        if status_value and " (" in status_value:
            status_value = status_value.split(" (")[0]

        # 筛选数据
        filtered_data = []
        for item in data:
            # 国家
            if country_value != "全部国家":
                if item.get("country") != country_value:
                    continue

            # 状态
            if status_value != "全部":
                if item.get("status") != status_value:
                    continue

            # 优质代理
            if good_proxy_checkbox.value:
                try:
                    latency = float(item.get("latency", "0").replace("ms", ""))
                    if latency >= 2000:
                        continue
                except:
                    continue

            filtered_data.append(item)
        
        # 按分数排序（从高到低）
        filtered_data.sort(key=lambda x: x.get("score", 0), reverse=True)
        
        # 添加到表格
        for item in filtered_data:
            table_list.controls.append(proxy_row(item, on_click_callback=on_proxy_selected))

        table_list.update()

    country_dropdown.on_change = refresh_table
    status_dropdown.on_change = refresh_table
    good_proxy_checkbox.on_change = refresh_table

    # ---------- 左侧导航（代理流程图）----------
    # 代理服务器节点状态和容器引用
    proxy_server_1_selected = {"value": False, "container": None}
    proxy_server_2_selected = {"value": False, "container": None}
    proxy_server_3_selected = {"value": False, "container": None}
    proxy_server_1_text = ft.Text("代理服务器", size=11, color=ft.Colors.WHITE, text_align=ft.TextAlign.CENTER)
    proxy_server_2_text = ft.Text("代理服务器(1)", size=11, color=ft.Colors.WHITE, text_align=ft.TextAlign.CENTER)
    proxy_server_3_text = ft.Text("代理服务器(2)", size=11, color=ft.Colors.WHITE, text_align=ft.TextAlign.CENTER)
    
    proxy_server_1_ip = ft.Text("未选择", size=9, color="#B39DDB", text_align=ft.TextAlign.CENTER)
    proxy_server_2_ip = ft.Text("未选择", size=9, color="#B39DDB", text_align=ft.TextAlign.CENTER)
    proxy_server_3_ip = ft.Text("未选择", size=9, color="#B39DDB", text_align=ft.TextAlign.CENTER)
    
    def create_flow_node(label, status="idle", subtitle_widget=None, clickable=False, node_id=None):
        """创建流程节点
        status: idle(空闲-灰色), active(活动-绿色), error(错误-红色), selected(选中-紫色)
        subtitle_widget: 副标题控件（如IP地址）
        clickable: 是否可点击
        node_id: 节点ID，用于识别哪个代理服务器
        """
        colors = {
            "idle": "#7E57C2",
            "active": "#66BB6A",
            "error": "#EF5350",
            "selected": "#AB47BC",
        }
        
        bg_colors = {
            "idle": "#2D1B4E",
            "active": "#2E7D32",
            "error": "#C62828",
            "selected": "#6A1B9A",
        }
        
        content_controls = [
            ft.Text(
                label,
                size=11,
                color=ft.Colors.WHITE,
                text_align=ft.TextAlign.CENTER,
            )
        ]
        
        if subtitle_widget:
            content_controls.append(subtitle_widget)
        
        node_container = ft.Container(
            width=100,
            height=60,
            border=ft.border.all(2, colors.get(status, ft.Colors.GREY_400)),
            border_radius=30,
            bgcolor=bg_colors.get(status, ft.Colors.BLACK38),
            alignment=ft.alignment.center,
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=2,
                controls=content_controls,
            ),
        )
        
        # 如果可点击，添加点击事件
        if clickable and node_id:
            def on_click(e):
                if node_id == "proxy1":
                    proxy_server_1_selected["value"] = not proxy_server_1_selected["value"]
                    proxy_server_1_selected["container"] = node_container
                    if proxy_server_1_selected["value"]:
                        node_container.border = ft.border.all(2, "#AB47BC")
                        node_container.bgcolor = "#6A1B9A"
                        append_log("[选择] 代理服务器已选中，请在右侧表格点击选择代理")
                    else:
                        node_container.border = ft.border.all(2, "#7E57C2")
                        node_container.bgcolor = "#2D1B4E"
                        append_log("[选择] 取消选中代理服务器")
                    node_container.update()
                elif node_id == "proxy2":
                    proxy_server_2_selected["value"] = not proxy_server_2_selected["value"]
                    proxy_server_2_selected["container"] = node_container
                    if proxy_server_2_selected["value"]:
                        node_container.border = ft.border.all(2, "#AB47BC")
                        node_container.bgcolor = "#6A1B9A"
                        append_log("[选择] 代理服务器(1)已选中，请在右侧表格点击选择代理")
                    else:
                        node_container.border = ft.border.all(2, "#7E57C2")
                        node_container.bgcolor = "#2D1B4E"
                        append_log("[选择] 取消选中代理服务器(1)")
                    node_container.update()
                elif node_id == "proxy3":
                    proxy_server_3_selected["value"] = not proxy_server_3_selected["value"]
                    proxy_server_3_selected["container"] = node_container
                    if proxy_server_3_selected["value"]:
                        node_container.border = ft.border.all(2, "#AB47BC")
                        node_container.bgcolor = "#6A1B9A"
                        append_log("[选择] 代理服务器(2)已选中，请在右侧表格点击选择代理")
                    else:
                        node_container.border = ft.border.all(2, "#7E57C2")
                        node_container.bgcolor = "#2D1B4E"
                        append_log("[选择] 取消选中代理服务器(2)")
                    node_container.update()
            
            node_container.on_click = on_click
            node_container.ink = True
        
        return node_container
    
    def create_arrow(direction="down"):
        """创建箭头"""
        return ft.Container(
            width=2,
            height=20,
            bgcolor="#7E57C2",
            alignment=ft.alignment.center,
        )
    
    # 单层代理流程
    single_layer_flow = ft.Column(
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=5,
        controls=[
            ft.Container(height=10),
            create_flow_node("公网IP", "idle", public_ip_text),
            create_arrow(),
            create_flow_node("代理服务器", "idle", proxy_server_1_ip, clickable=True, node_id="proxy1"),
            create_arrow(),
            create_flow_node("Internet", "idle"),
        ],
    )
    
    # 多层代理流程
    multi_layer_flow = ft.Column(
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=5,
        controls=[
            ft.Container(height=10),
            create_flow_node("公网IP", "idle", public_ip_text),
            create_arrow(),
            create_flow_node("代理服务器(1)", "idle", proxy_server_2_ip, clickable=True, node_id="proxy2"),
            create_arrow(),
            create_flow_node("代理服务器(2)", "idle", proxy_server_3_ip, clickable=True, node_id="proxy3"),
            create_arrow(),
            create_flow_node("Internet", "idle"),
        ],
    )
    
    # 流程容器（用于切换）
    flow_container = ft.Container(
        expand=True,
        content=single_layer_flow,
    )
    
    # 代理模式切换函数
    def switch_to_single(e):
        # 如果代理正在运行，弹出确认对话框
        if proxy_running["value"]:
            def close_dialog(confirm):
                dialog.open = False
                page.update()
                
                if confirm:
                    # 停止代理服务器
                    append_log("[停止] 切换链路，停止代理服务...")
                    server.stop_proxy_server()
                    proxy_running["value"] = False
                    start_button.text = "启动"
                    start_button.bgcolor = "#4ea7d8"
                    start_button.update()
                    
                    # 切换模式
                    flow_container.content = single_layer_flow
                    append_log("[模式] 切换到单层代理模式")
                    flow_container.update()
                    
                    # 启用轮换按钮
                    rotation_button.disabled = False
                    rotation_interval.disabled = False
                    rotation_button.update()
                    rotation_interval.update()
            
            dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text("确认切换"),
                content=ft.Text("切换链路会停止当前的代理服务，是否继续？"),
                actions=[
                    ft.TextButton("取消", on_click=lambda e: close_dialog(False)),
                    ft.TextButton("确认", on_click=lambda e: close_dialog(True)),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            page.overlay.append(dialog)
            dialog.open = True
            page.update()
        else:
            flow_container.content = single_layer_flow
            append_log("[模式] 切换到单层代理模式")
            flow_container.update()
            
            # 启用轮换按钮
            rotation_button.disabled = False
            rotation_interval.disabled = False
            rotation_button.update()
            rotation_interval.update()
    
    def switch_to_multi(e):
        # 如果代理正在运行，弹出确认对话框
        if proxy_running["value"]:
            def close_dialog(confirm):
                dialog.open = False
                page.update()
                
                if confirm:
                    # 停止代理服务器
                    append_log("[停止] 切换链路，停止代理服务...")
                    server.stop_proxy_server()
                    proxy_running["value"] = False
                    start_button.text = "启动"
                    start_button.bgcolor = "#4ea7d8"
                    start_button.update()
                    
                    # 切换模式
                    flow_container.content = multi_layer_flow
                    append_log("[模式] 切换到多层代理模式")
                    flow_container.update()
                    
                    # 禁用轮换按钮
                    rotation_button.disabled = True
                    rotation_interval.disabled = True
                    rotation_button.update()
                    rotation_interval.update()
            
            dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text("确认切换"),
                content=ft.Text("切换链路会停止当前的代理服务，是否继续？"),
                actions=[
                    ft.TextButton("取消", on_click=lambda e: close_dialog(False)),
                    ft.TextButton("确认", on_click=lambda e: close_dialog(True)),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            page.overlay.append(dialog)
            dialog.open = True
            page.update()
        else:
            flow_container.content = multi_layer_flow
            append_log("[模式] 切换到多层代理模式")
            flow_container.update()
            
            # 禁用轮换按钮
            rotation_button.disabled = True
            rotation_interval.disabled = True
            rotation_button.update()
            rotation_interval.update()
    
    # 代理模式菜单
    proxy_mode_menu = ft.PopupMenuButton(
        icon=ft.Icons.MORE_VERT,
        icon_size=18,
        icon_color="#CE93D8",
        items=[
            ft.PopupMenuItem(
                text="单层代理",
                icon=ft.Icons.ARROW_FORWARD,
                on_click=switch_to_single,
            ),
            ft.PopupMenuItem(
                text="多层代理",
                icon=ft.Icons.MULTIPLE_STOP,
                on_click=switch_to_multi,
            ),
        ],
        menu_position=ft.PopupMenuPosition.UNDER,
    )
    
    # 代理服务器运行状态
    proxy_running = {"value": False}
    
    def toggle_proxy_server(e):
        """启动/停止代理服务器"""
        if not proxy_running["value"]:
            # 启动代理服务器
            # 判断当前模式
            current_mode = flow_container.content
            
            if current_mode == single_layer_flow:
                # 单层代理模式
                proxy_address = proxy_server_1_ip.value
                
                if proxy_address == "未选择":
                    append_log("[错误] 请先选择代理服务器")
                    return
                
                append_log("[启动] 单层代理模式")
                append_log(f"[启动] 上游代理: {proxy_address}")
                
                # 解析协议
                protocol = "socks5"  # 默认使用socks5
                
                # 在后台线程启动服务器
                def start_server():
                    success = server.start_proxy_server(
                        proxy_address,
                        protocol,
                        log_callback=lambda msg: append_log(f"[服务器] {msg}")
                    )
                    
                    if success:
                        proxy_running["value"] = True
                        start_button.text = "停止"
                        start_button.bgcolor = "#EF5350"
                        start_button.update()
                        append_log(f"[启动] 代理服务器启动成功")
                        append_log(f"[启动] SOCKS5: 127.0.0.1:{socks5_port}")
                        append_log(f"[启动] HTTP: 127.0.0.1:{http_port}")
                    else:
                        append_log("[错误] 代理服务器启动失败")
                
                threading.Thread(target=start_server, daemon=True).start()
                
            else:
                # 多层代理模式
                append_log("[提示] 多层代理模式暂未实现")
        else:
            # 停止代理服务器
            append_log("[停止] 正在停止代理服务器...")
            server.stop_proxy_server()
            proxy_running["value"] = False
            start_button.text = "启动"
            start_button.bgcolor = "#4ea7d8"
            start_button.update()
            append_log("[停止] 代理服务器已停止")
    
    start_button = ft.ElevatedButton(
        "启动",
        width=120,
        height=40,
        bgcolor="#9C27B0",
        color=ft.Colors.WHITE,
        on_click=toggle_proxy_server,
    )
    
    # 获取服务器端口配置
    socks5_port, http_port = server.get_server_ports()
    
    # 端口信息显示
    port_info_text = ft.Text(
        f"代理服务\nSocks5:{socks5_port} / Http:{http_port}",
        size=10,
        color="#fcf8fc",
        text_align=ft.TextAlign.CENTER,
    )
    
    left_nav = ft.Container(
        width=150,
        bgcolor="#2D1B4E",
        padding=10,
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=0,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.CENTER,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=5,
                    controls=[
                        ft.Text(
                            "代理链路",
                            size=14,
                            weight=ft.FontWeight.BOLD,
                            color="#fcf8fc",
                        ),
                        proxy_mode_menu,
                    ],
                ),
                ft.Divider(height=1, color="#4A2C6D"),
                flow_container,
                ft.Container(height=10),
                port_info_text,
                ft.Container(height=5),
                start_button,
            ],
        ),
    )

    # ---------- 顶部栏 ----------
    # ---------- IP轮换功能 ----------
    rotation_running = {"value": False, "timer": None}
    
    rotation_interval = ft.TextField(
        value="10",
        width=60,
        height=35,
        text_size=12,
        text_align=ft.TextAlign.CENTER,
        color=ft.Colors.WHITE,
        border_color=ft.Colors.GREY_400,
        content_padding=ft.padding.symmetric(horizontal=5, vertical=5),
    )
    
    rotation_button = ft.ElevatedButton(
        "启用轮换",
        bgcolor="#BA68C8",
        color=ft.Colors.WHITE,
        height=35,
    )
    
    def toggle_ip_rotation(e):
        """启用/停止IP轮换"""
        # 检查是否为单层代理模式
        if flow_container.content != single_layer_flow:
            append_log("[轮换] IP轮换仅支持单层代理模式")
            return
        
        if not rotation_running["value"]:
            # 启用轮换
            try:
                interval = int(rotation_interval.value)
                if interval < 1:
                    append_log("[轮换] 间隔时间必须大于0秒")
                    return
            except ValueError:
                append_log("[轮换] 请输入有效的数字")
                return
            
            if not data:
                append_log("[轮换] 没有可用的代理")
                return
            
            # 筛选可用代理
            available_proxies = [item for item in data if item.get("status") == "可用"]
            if not available_proxies:
                append_log("[轮换] 没有可用的代理")
                return
            
            rotation_running["value"] = True
            rotation_running["current_index"] = 0
            rotation_running["proxies"] = available_proxies
            
            rotation_button.text = "停止轮换"
            rotation_button.bgcolor = "#EF5350"
            rotation_button.update()
            
            append_log(f"[轮换] 启用IP轮换，间隔 {interval} 秒，共 {len(available_proxies)} 个代理")
            
            # 立即切换到第一个代理
            switch_to_next_proxy()
            
            # 启动定时器
            def rotation_timer():
                import time
                while rotation_running["value"]:
                    time.sleep(interval)
                    if rotation_running["value"]:
                        switch_to_next_proxy()
            
            rotation_running["timer"] = threading.Thread(target=rotation_timer, daemon=True)
            rotation_running["timer"].start()
        else:
            # 停止轮换
            rotation_running["value"] = False
            rotation_button.text = "启用轮换"
            rotation_button.bgcolor = "#BA68C8"
            rotation_button.update()
            append_log("[轮换] 已停止IP轮换")
    
    def switch_to_next_proxy():
        """切换到下一个代理"""
        if not rotation_running["value"]:
            return
        
        proxies = rotation_running["proxies"]
        current_index = rotation_running["current_index"]
        
        # 获取下一个代理
        proxy_item = proxies[current_index]
        address = proxy_item.get("address", "")
        protocol = proxy_item.get("protocol", "socks5").lower()
        
        # 更新左侧显示
        proxy_server_1_ip.value = address
        proxy_server_1_ip.update()
        
        # 如果代理服务器正在运行，切换上游代理
        if proxy_running["value"]:
            server.switch_upstream_proxy(address, protocol)
            append_log(f"[轮换] 切换到 {address}")
        else:
            append_log(f"[轮换] 下一个代理: {address} (代理服务未启动)")
        
        # 更新索引
        rotation_running["current_index"] = (current_index + 1) % len(proxies)
    
    rotation_button.on_click = toggle_ip_rotation
    
    # ---------- 顶部栏 ----------
    top_bar = ft.Container(
        height=65,
        bgcolor="#2A1A3D",
        padding=5,
        content=ft.Row(
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=5,
            controls=[
                country_dropdown,
                status_dropdown,
                good_proxy_checkbox,
                ft.Container(expand=True),
                ft.Row(
                    spacing=5,
                    controls=[
                        rotation_button,
                        rotation_interval,
                        ft.Text("秒", size=12, color="#B39DDB"),
                    ],
                ),
            ],
        ),
    )

    # ---------- 表格区 ----------
    # 进度条
    test_progress = ft.ProgressBar(
        width=630,
        height=4,
        value=0,
        color="#AB47BC",
        bgcolor="#4A2C6D",
    )
    
    table_area = ft.Container(
        expand=True,
        bgcolor="#1A0B2E",
        padding=10,
        content=ft.Column(
            expand=True,
            spacing=5,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Text("代 理 列 表", weight=ft.FontWeight.BOLD, color="#fcf8fc", size=14),
                        test_progress,
                    ],
                ),
                ft.Container(
                    expand=True,
                    bgcolor="#2D1B4E",
                    border_radius=8,
                    content=ft.Column(
                        expand=True,
                        spacing=0,
                        controls=[
                            # 固定表头
                            header_row,
                            # 可滚动内容
                            ft.Container(
                                expand=True,
                                content=table_list,
                            ),
                        ],
                    ),
                ),
            ],
        ),
    )

    # ---------- 底部 ----------
    bottom = ft.Container(
        height=100,
        bgcolor="#2A1A3D",
        padding=10,
        content=ft.Row(
            spacing=10,
            controls=[
                ft.Container(
                    expand=True,
                    bgcolor="#1A0B2E",
                    padding=4,
                    border=ft.border.all(1, "#4A2C6D"),
                    border_radius=4,
                    content=log_list,
                ),
                ft.Container(
                    width=250,
                    content=ft.Column(
                        spacing=5,
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.ElevatedButton("获取在线代理", expand=True, bgcolor="#7E57C2", color=ft.Colors.WHITE),
                                    ft.ElevatedButton(
                                        "导入代理",
                                        expand=True,
                                        bgcolor="#9C27B0",
                                        color=ft.Colors.WHITE,
                                        on_click=lambda e: file_picker.pick_files(
                                            allow_multiple=False, allowed_extensions=["txt"]
                                        ),
                                    ),
                                ]
                            ),
                            ft.Row(
                                controls=[
                                    ft.ElevatedButton(
                                        "清空列表",
                                        expand=True,
                                        bgcolor="#EF5350",
                                        color=ft.Colors.WHITE,
                                        on_click=lambda e: (
                                            table_list.controls.clear(),
                                            table_list.update(),
                                        ),
                                    ),
                                    ft.Container(
                                        expand=True,
                                        alignment=ft.alignment.center,
                                        content=more_menu,
                                    ),
                                ]
                            ),
                        ],
                    ),
                ),
            ],
        ),
    )

    # ---------- 右侧 ----------
    right_content = ft.Column(
        expand=True,
        spacing=0,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=[top_bar, table_area, bottom],
    )

    # ---------- 页面 ----------
    page.add(
        ft.Row(
            expand=True,
            spacing=0,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
            controls=[left_nav, right_content],
        )
    )

    # 页面添加后，更新筛选选项
    update_filter_options()
    
    refresh_table()


ft.app(target=main)
