import system.scheduler
import app
import math
import time
import display
from system.eventbus import eventbus
from events.input import BUTTON_TYPES, ButtonDownEvent, Buttons
try:
    from system.hexpansion.events import HexpansionMountedEvent, HexpansionUnmountedEvent
except ImportError:
    HexpansionMountedEvent = None
    HexpansionUnmountedEvent = None

STATE_MENU        = 0
STATE_PORT_SELECT = 1
STATE_DUAL_DEMO   = 2
STATE_FAQ         = 3

COLOR_BG_NAVY     = (0.04, 0.06, 0.14)
COLOR_CARD_BG     = (0.08, 0.14, 0.28)
COLOR_CYAN        = (0.00, 0.90, 1.00)
COLOR_GOLD        = (1.00, 0.80, 0.10)
COLOR_GREEN       = (0.10, 0.95, 0.40)
COLOR_WHITE       = (1.00, 1.00, 1.00)
COLOR_GRAY        = (0.50, 0.60, 0.75)
COLOR_RED         = (1.00, 0.25, 0.25)

MENU_ITEMS = [
    "Mirror to HDMI",
    "Mirror to 2nd Screen",
    "Dual-Screen Demo",
    "Detach All Mirrors",
    "Dual Mirror FAQ",
]

BOOT_PY_TEMPLATE = """# This file is executed on every boot (including wake-boot from deepsleep)
import display

try:
    display.attach_mirror(port={port}, baudrate={baud}, raw={raw})
    print("[BOOT] Mirror auto-attached on Port {port}")
except Exception as e:
    print("[BOOT] Mirror attach skipped:", e)
"""

BOOT_PY_STANDALONE = """# This file is executed on every boot (including wake-boot from deepsleep)
# Standalone mode - no active display mirrors
"""

class DisplayManagerApp(app.App):
    def __init__(self):
        super().__init__()
        self.button_states = Buttons(self)
        
        self.state = STATE_MENU
        self.selected_menu_idx = 0
        self.target_mode = "HDMI"
        self.selected_port = 1
        self.status_msg = "Select an option"
        self.status_color = COLOR_CYAN
        
        # Dual-screen demo state
        self.sec_screen = None
        self.demo_angle = 0.0
        self.demo_speed = 1.0
        self.demo_frame = 0
        self.demo_target_port = 1
        self.demo_target_raw = False
        
        # Mirror tracking & hot-plug detection
        self.active_mirror_mode = None
        self.active_mirror_port = None
        self.last_detected_screen_port = None
        self.hotplug_poll_timer = 0.0
        
        # Event listener
        eventbus.on(ButtonDownEvent, self.handle_button_down, self)
        if HexpansionMountedEvent:
            eventbus.on(HexpansionMountedEvent, self.handle_hexpansion_mounted, self)
        if HexpansionUnmountedEvent:
            eventbus.on(HexpansionUnmountedEvent, self.handle_hexpansion_unmounted, self)
        
        # Query active status
        self._refresh_active_status()

    def _refresh_active_status(self):
        active_ports = []
        for p in range(1, 7):
            try:
                if display.is_mirror_active(p):
                    active_ports.append(p)
            except: pass
        if active_ports:
            p = active_ports[0]
            self.active_mirror_port = p
            det = self._detect_screen_port()
            if det == p:
                self.active_mirror_mode = "SCREEN"
                self.last_detected_screen_port = p
                self.status_msg = f"Screen Mirror: Port {p}"
            else:
                self.active_mirror_mode = "HDMI"
                self.status_msg = f"HDMI Mirror: Port {p}"
            self.status_color = COLOR_GREEN
        else:
            self.active_mirror_port = None
            self.active_mirror_mode = None
            self.last_detected_screen_port = None
            self.status_msg = "No mirror currently active"
            self.status_color = COLOR_GRAY

    def _save_persistent_boot(self, port, baud, raw, sck=None, mosi=None):
        try:
            with open("/boot.py", "w") as f:
                if sck is not None and mosi is not None:
                    f.write(f"""# This file is executed on every boot (including wake-boot from deepsleep)
import display

try:
    display.attach_mirror(port={port}, sck={sck}, mosi={mosi}, baudrate={baud}, raw={raw})
    print("[BOOT] Mirror auto-attached on Port {port} (sck={sck}, mosi={mosi})")
except Exception as e:
    print("[BOOT] Mirror attach skipped:", e)
""")
                else:
                    f.write(f"""# This file is executed on every boot (including wake-boot from deepsleep)
import display

try:
    display.attach_mirror(port={port}, baudrate={baud}, raw={raw})
    print("[BOOT] Mirror auto-attached on Port {port}")
except Exception as e:
    print("[BOOT] Mirror attach skipped:", e)
""")
        except Exception as e:
            print("Failed to update boot.py:", e)

    def _clear_persistent_boot(self):
        try:
            with open("/boot.py", "w") as f:
                f.write(BOOT_PY_STANDALONE)
        except Exception as e:
            print("Failed to reset boot.py:", e)

    def handle_button_down(self, event: ButtonDownEvent):
        btn = event.button
        is_up      = BUTTON_TYPES["UP"] in btn
        is_down    = BUTTON_TYPES["DOWN"] in btn
        is_confirm = BUTTON_TYPES["CONFIRM"] in btn
        is_cancel  = BUTTON_TYPES["CANCEL"] in btn
        is_right   = BUTTON_TYPES["RIGHT"] in btn
        is_left    = BUTTON_TYPES["LEFT"] in btn
        
        if self.state == STATE_MENU:
            if is_up:
                self.selected_menu_idx = (self.selected_menu_idx - 1) % len(MENU_ITEMS)
            elif is_down:
                self.selected_menu_idx = (self.selected_menu_idx + 1) % len(MENU_ITEMS)
            elif is_confirm or is_right:
                self._activate_menu_selection()
            elif is_cancel or is_left:
                self.minimise()

        elif self.state == STATE_PORT_SELECT:
            if is_up or is_right:
                self.selected_port = ((self.selected_port) % 6) + 1
            elif is_down or is_left:
                self.selected_port = ((self.selected_port - 2) % 6) + 1
            elif is_confirm:
                self._execute_port_action()
            elif is_cancel:
                self.state = STATE_MENU

        elif self.state == STATE_DUAL_DEMO:
            if is_cancel or is_confirm:
                self._stop_dual_demo()
            elif is_up:
                self.demo_speed = min(3.0, self.demo_speed + 0.5)
            elif is_down:
                self.demo_speed = max(0.2, self.demo_speed - 0.5)

        elif self.state == STATE_FAQ:
            if is_cancel or is_confirm or is_left or is_right:
                self.state = STATE_MENU

    def _detect_screen_port(self):
        try:
            from system.hexpansion.util import get_slots_by_vid_pid
            slots = get_slots_by_vid_pid(0x4D42, 0x5EE5)
            if slots:
                return slots[0]
        except Exception:
            pass
        try:
            from machine import I2C
            from system.hexpansion.util import read_hexpansion_header
            for p in range(1, 7):
                try:
                    i2c = I2C(p)
                    devs = i2c.scan()
                    if 0x50 in devs:
                        hdr = read_hexpansion_header(i2c, 0x50)
                        if hdr and hdr.vid == 0x4D42 and hdr.pid == 0x5EE5:
                            return p
                except Exception:
                    pass
        except Exception:
            pass
        return None

    def _activate_menu_selection(self):
        idx = self.selected_menu_idx
        if idx == 0: # HDMI Mirror
            self.target_mode = "HDMI"
            self.selected_port = 1
            self.state = STATE_PORT_SELECT
        elif idx == 1: # Screen Hexp Mirror
            self.target_mode = "SCREEN"
            det = self._detect_screen_port()
            self.selected_port = det if det is not None else 4
            self.state = STATE_PORT_SELECT
        elif idx == 2: # Dual-Screen Demo
            self.target_mode = "DEMO"
            det = self._detect_screen_port()
            self.selected_port = det if det is not None else 4
            self.state = STATE_PORT_SELECT
        elif idx == 3: # Detach
            display.detach_mirror(0)
            self._clear_persistent_boot()
            self.status_msg = "All mirrors detached"
            self.status_color = COLOR_RED
            self._refresh_active_status()
        elif idx == 4: # FAQ
            self.state = STATE_FAQ

    def _attach_screen_mirror(self, port):
        time.sleep_ms(150)
        try:
            display.detach_mirror(0)
            display.attach_mirror(port=port, baudrate=40000000, raw=True)
            self._save_persistent_boot(port=port, baud=40000000, raw=True)
            self.status_msg = f"Screen Mirror: Port {port}"
            self.status_color = COLOR_GREEN
            self.active_mirror_mode = "SCREEN"
            self.active_mirror_port = port
            self.last_detected_screen_port = port
            print(f"[MIRROR] Screen mirror attached on Port {port}")
        except Exception as e:
            print(f"Failed to attach mirror on Port {port}:", e)
            self.status_msg = f"Attach error: {e}"
            self.status_color = COLOR_RED

    def handle_hexpansion_mounted(self, event):
        if self.active_mirror_mode == "SCREEN":
            is_screen = False
            if hasattr(event, "header") and event.header:
                if event.header.vid == 0x4D42 and event.header.pid == 0x5EE5:
                    is_screen = True
            if not is_screen:
                det = self._detect_screen_port()
                if det == event.port:
                    is_screen = True
            if is_screen:
                print(f"[EVENT] Screen hexpansion mounted on Port {event.port}")
                self._attach_screen_mirror(event.port)

    def handle_hexpansion_unmounted(self, event):
        if self.active_mirror_mode == "SCREEN" and event.port == self.active_mirror_port:
            print(f"[EVENT] Screen hexpansion unmounted from Port {event.port}")
            self.last_detected_screen_port = None
            self.status_msg = f"Screen Port {event.port} unplugged"
            self.status_color = COLOR_GRAY

    def _execute_port_action(self):
        port = self.selected_port
        
        if self.target_mode == "HDMI":
            try:
                display.detach_mirror(0)
                display.attach_mirror(port=port, baudrate=10000000, raw=False)
                self._save_persistent_boot(port=port, baud=10000000, raw=False)
                self.status_msg = f"HDMI Mirror on Port {port}"
                self.status_color = COLOR_GREEN
                self.active_mirror_mode = "HDMI"
                self.active_mirror_port = port
            except Exception as e:
                self.status_msg = f"Error: {e}"
                self.status_color = COLOR_RED
            self.state = STATE_MENU

        elif self.target_mode == "SCREEN":
            self._attach_screen_mirror(port)
            self.state = STATE_MENU

        elif self.target_mode == "DEMO":
            self.demo_target_port = port
            self.demo_target_raw = False if port == 1 else True
            self._start_dual_demo()

    def _start_dual_demo(self):
        display.detach_mirror(0)
        try:
            baud = 10000000 if not self.demo_target_raw else 40000000
            self.sec_screen = display.Screen(port=self.demo_target_port, width=240, height=240,
                                             baudrate=baud, raw=self.demo_target_raw)
            self.demo_frame = 0
            self.state = STATE_DUAL_DEMO
        except Exception as e:
            self.status_msg = f"Screen init failed: {e}"
            self.status_color = COLOR_RED
            self.state = STATE_MENU

    def _stop_dual_demo(self):
        if self.sec_screen:
            try:
                self.sec_screen.deinit()
            except: pass
            self.sec_screen = None
        self.state = STATE_MENU
        self.status_msg = "Dual-display demo finished"
        self.status_color = COLOR_CYAN

    def update(self, delta):
        # Hot-plug detection fallback:
        self.hotplug_poll_timer += delta
        if self.hotplug_poll_timer >= 1.0:
            self.hotplug_poll_timer = 0.0
            if self.active_mirror_mode == "SCREEN":
                detected = self._detect_screen_port()
                if detected is not None:
                    if detected != self.last_detected_screen_port or not display.is_mirror_active(detected):
                        print(f"[HOTPLUG POLL] Screen detected on Port {detected}")
                        self._attach_screen_mirror(detected)
                else:
                    if self.last_detected_screen_port is not None:
                        print(f"[HOTPLUG POLL] Screen disconnected from Port {self.last_detected_screen_port}")
                        self.last_detected_screen_port = None
                        self.status_msg = "Screen unplugged"
                        self.status_color = COLOR_GRAY

        if self.state == STATE_DUAL_DEMO and self.sec_screen:
            self.demo_angle += 0.04 * self.demo_speed
            self.demo_frame += 1
            
            # Render independent secondary screen
            try:
                ctx2 = self.sec_screen.get_ctx()
                ctx2.text_align = ctx2.CENTER
                ctx2.text_baseline = ctx2.MIDDLE
                
                # Dark cyan/purple tech background
                ctx2.rgb(0.05, 0.08, 0.18).rectangle(-120, -120, 240, 240).fill()
                
                # Rotating 3D wireframe diamond
                rot = self.demo_angle
                r_outer = 65.0
                
                pts = [
                    (r_outer * math.cos(rot), r_outer * math.sin(rot) * 0.5),
                    (r_outer * math.cos(rot + 1.57), r_outer * math.sin(rot + 1.57) * 0.5),
                    (r_outer * math.cos(rot + 3.14), r_outer * math.sin(rot + 3.14) * 0.5),
                    (r_outer * math.cos(rot + 4.71), r_outer * math.sin(rot + 4.71) * 0.5),
                ]
                top_pt = (0, -60.0)
                bot_pt = (0,  60.0)
                
                # Draw diamond edges
                ctx2.line_width = 2.0
                ctx2.rgb(0.0, 0.9, 1.0)
                for pt in pts:
                    ctx2.begin_path().move_to(top_pt[0], top_pt[1]).line_to(pt[0], pt[1]).stroke()
                    ctx2.begin_path().move_to(bot_pt[0], bot_pt[1]).line_to(pt[0], pt[1]).stroke()
                for k in range(4):
                    p1, p2 = pts[k], pts[(k+1)%4]
                    ctx2.begin_path().move_to(p1[0], p1[1]).line_to(p2[0], p2[1]).stroke()
                
                # Central core
                pulse = 12.0 + 4.0 * math.sin(rot * 2)
                ctx2.rgb(1.0, 0.8, 0.0).arc(0, 0, pulse, 0, 6.283, 0).fill()
                
                # Header & telemetry on secondary display
                ctx2.font_size = 13
                ctx2.rgb(1.0, 1.0, 1.0).move_to(0, -90).text("SECONDARY DISPLAY")
                ctx2.font_size = 11
                ctx2.rgb(0.5, 0.8, 1.0).move_to(0, 95).text(f"PORT {self.demo_target_port} | FR {self.demo_frame}")
                
                self.sec_screen.end_frame(ctx2)
            except Exception as e:
                print("Secondary draw error:", e)
        return True

    def draw(self, ctx):
        ctx.save()
        
        # Origin (0, 0) is ALREADY at screen center (-120 to +120)
        # Background fill
        ctx.rgb(*COLOR_BG_NAVY).rectangle(-120, -120, 240, 240).fill()
        
        # Outer bezel circle
        ctx.rgb(0.12, 0.18, 0.32).line_width = 1.5
        ctx.begin_path().arc(0, 0, 119, 0, 6.283, 0).stroke()
        
        if self.state == STATE_MENU:
            self._draw_main_menu(ctx)
        elif self.state == STATE_PORT_SELECT:
            self._draw_port_select(ctx)
        elif self.state == STATE_DUAL_DEMO:
            self._draw_dual_demo_primary(ctx)
        elif self.state == STATE_FAQ:
            self._draw_faq(ctx)
            
        ctx.restore()

    def _draw_main_menu(self, ctx):
        ctx.text_align = ctx.CENTER
        ctx.text_baseline = ctx.MIDDLE
        
        # Title
        ctx.font_size = 15
        ctx.rgb(*COLOR_CYAN).move_to(0, -85).text("DISPLAY MANAGER")
        
        # Menu items list
        y_start = -48
        box_w = 186
        box_h = 23
        
        for i, title in enumerate(MENU_ITEMS):
            y = y_start + i * 26
            is_sel = (i == self.selected_menu_idx)
            
            if is_sel:
                # Centered rounded card around text
                ctx.rgb(*COLOR_CARD_BG)
                ctx.round_rectangle(-box_w // 2, y - box_h // 2, box_w, box_h, 5).fill()
                ctx.rgb(*COLOR_GOLD).line_width = 1.5
                ctx.round_rectangle(-box_w // 2, y - box_h // 2, box_w, box_h, 5).stroke()
                
                ctx.rgb(*COLOR_GOLD)
                ctx.font_size = 13
                ctx.move_to(0, y).text(f"> {title} <")
            else:
                ctx.rgb(*COLOR_WHITE)
                ctx.font_size = 12
                ctx.move_to(0, y).text(title)
        
        # Status / active banner
        ctx.font_size = 11
        ctx.rgb(*self.status_color).move_to(0, 78).text(self.status_msg)
        
        # Controls footer
        ctx.font_size = 10
        ctx.rgb(*COLOR_GRAY).move_to(0, 98).text("A/D: Nav   C: Select   F: Exit")

    def _draw_port_select(self, ctx):
        ctx.text_align = ctx.CENTER
        ctx.text_baseline = ctx.MIDDLE
        
        # Title & Target Mode
        ctx.font_size = 15
        ctx.rgb(*COLOR_CYAN).move_to(0, -88).text("SELECT PORT")
        
        mode_label = "HDMI Mirror" if self.target_mode == "HDMI" else ("Screen Mirror" if self.target_mode == "SCREEN" else "Dual Demo")
        ctx.font_size = 12
        ctx.rgb(*COLOR_WHITE).move_to(0, -68).text(f"Target: {mode_label}")
        
        # Port number display box
        box_w = 110
        box_h = 44
        ctx.rgb(*COLOR_CARD_BG)
        ctx.round_rectangle(-box_w // 2, -22 - box_h // 2, box_w, box_h, 8).fill()
        ctx.rgb(*COLOR_GOLD).line_width = 2.0
        ctx.round_rectangle(-box_w // 2, -22 - box_h // 2, box_w, box_h, 8).stroke()
        
        ctx.font_size = 20
        ctx.rgb(*COLOR_GOLD).move_to(0, -22).text(f"PORT {self.selected_port}")
        
        try:
            pins = display.get_port_pins(self.selected_port)
            p_text = f"SCK:{pins['sck']} MOSI:{pins['mosi']} CS:{pins['cs']} DC:{pins['dc']}"
        except:
            p_text = "Standard Hexpansion Pinout"
            
        ctx.font_size = 10
        ctx.rgb(*COLOR_GRAY).move_to(0, 16).text(p_text)
        ctx.rgb(*COLOR_GREEN).move_to(0, 38).text("(Persists across reboots in boot.py)")
        
        ctx.font_size = 11
        ctx.rgb(*COLOR_WHITE).move_to(0, 76).text("A/D: Change Port")
        ctx.rgb(*COLOR_CYAN).move_to(0, 96).text("C: Activate    F: Back")

    def _draw_dual_demo_primary(self, ctx):
        ctx.text_align = ctx.CENTER
        ctx.text_baseline = ctx.MIDDLE
        
        ctx.font_size = 15
        ctx.rgb(*COLOR_GOLD).move_to(0, -88).text("PRIMARY DISPLAY")
        ctx.font_size = 11
        ctx.rgb(*COLOR_WHITE).move_to(0, -70).text("Tildagon Round LCD")
        
        # Interactive rotating telemetry graphic on primary screen
        rot = -self.demo_angle
        ctx.line_width = 2.0
        ctx.rgb(*COLOR_CYAN)
        for i in range(6):
            ang = rot + i * 1.047
            x1 = 26 * math.cos(ang)
            y1 = 26 * math.sin(ang)
            x2 = 52 * math.cos(ang)
            y2 = 52 * math.sin(ang)
            ctx.begin_path().move_to(x1, y1).line_to(x2, y2).stroke()
        
        ctx.rgb(1.0, 0.4, 0.4).arc(0, 0, 15, 0, 6.283, 0).fill()
        
        ctx.font_size = 11
        ctx.rgb(*COLOR_GREEN).move_to(0, 75).text(f"2nd Screen Port: {self.demo_target_port}")
        ctx.rgb(*COLOR_WHITE).move_to(0, 95).text("A/D: Speed    F: Exit Demo")

    def _draw_faq(self, ctx):
        ctx.text_align = ctx.CENTER
        ctx.text_baseline = ctx.MIDDLE
        ctx.font_size = 14
        ctx.rgb(*COLOR_GOLD).move_to(0, -92).text("DUAL MIRROR FAQ")
        
        ctx.text_align = ctx.LEFT
        x = -96
        
        ctx.font_size = 11
        ctx.rgb(*COLOR_WHITE).move_to(x, -68).text("Can I mirror both at once?")
        ctx.font_size = 10
        ctx.rgb(*COLOR_CYAN).move_to(x, -52).text("- ESP32-S3 has 1 free SPI master")
        ctx.rgb(*COLOR_CYAN).move_to(x, -38).text("  controller (SPI2_HOST).")
        ctx.rgb(*COLOR_CYAN).move_to(x, -24).text("- Port 1 and 5 use different")
        ctx.rgb(*COLOR_CYAN).move_to(x, -10).text("  physical SCK & MOSI pins.")
        
        ctx.font_size = 11
        ctx.rgb(*COLOR_WHITE).move_to(x, 10).text("How to run both?")
        ctx.font_size = 10
        ctx.rgb(*COLOR_GREEN).move_to(x, 26).text("- Daisy-chain on same SPI bus")
        ctx.rgb(*COLOR_GREEN).move_to(x, 38).text("  with dual CS chip selects.")
        ctx.rgb(*COLOR_GREEN).move_to(x, 50).text("- Or switch ports per frame.")
        
        ctx.text_align = ctx.CENTER
        ctx.font_size = 11
        ctx.rgb(*COLOR_GRAY).move_to(0, 95).text("Press F or C to return")

__app_export__ = DisplayManagerApp
