import os
import multiprocessing
import webview
import tkinter as tk
from tkinterdnd2 import DND_FILES, TkinterDnD
import threading
import secrets
import re
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qs
import tkinter.simpledialog as sd

# --- 核心配置 ---
XOR_KEY = 0x66
TARGET_EXT = ".sm"
HEADER_SIZE = 32
CHUNK_SIZE = 1024 * 1024
MEDIA_EXTS = ['.mp4', '.webm', '.mov', '.jpg', '.jpeg', '.png', '.gif']


def crypt_data(data):
    key_map = bytes([i ^ XOR_KEY for i in range(256)])
    return data.translate(key_map)


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class DecryptServer(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_url = urlparse(self.path)
        query = parse_qs(parsed_url.query)
        token = query.get("token", [None])[0]

        if token != self.server.auth_token:
            self.send_response(403)
            self.end_headers()
            return

        if parsed_url.path == '/list':
            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            data = [{"name": os.path.basename(p)} for p in self.server.playlist]
            self.wfile.write(json.dumps(data).encode('utf-8'))
            return

        idx_str = query.get("idx", [0])[0]
        idx = int(idx_str) if idx_str.isdigit() else 0
        if idx >= len(self.server.playlist): idx = 0
        target_path = self.server.playlist[idx]

        if parsed_url.path == '/raw':
            self.handle_raw_stream(target_path)
            return

        self.handle_html_shell(target_path, token, idx)

    def handle_html_shell(self, file_path, token, idx):
        try:
            with open(file_path, 'rb') as f:
                header = crypt_data(f.read(HEADER_SIZE))
                orig_ext = header.decode('utf-8', errors='ignore').strip('\x00').lower()
        except:
            orig_ext = ""

        is_video = orig_ext in ['.mp4', '.webm', '.mov']
        media_src = f"/raw?token={token}&idx={idx}&_t={secrets.token_hex(4)}"

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body, html {{ margin: 0; padding: 0; width: 100%; height: 100%; background: #000; color: white; overflow: hidden; font-family: sans-serif; }}
                #viewer {{ width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; }}
                video, img {{ max-width: 100%; max-height: 100%; outline: none; }}
                #sidebar {{ 
                    position: fixed; right: 0; top: 0; width: 260px; height: 100%; 
                    background: rgba(15,15,15,0.9); border-left: 2px solid #2196F3;
                    transform: translateX(255px); transition: 0.3s cubic-bezier(0,0,0,1); z-index: 1000;
                    padding: 15px; box-sizing: border-box; overflow-y: auto;
                }}
                #sidebar:hover {{ transform: translateX(0); }}
                .item {{ padding: 10px; cursor: pointer; border-bottom: 1px solid #333; font-size: 13px; opacity: 0.7; word-break: break-all; }}
                .item:hover {{ opacity: 1; background: #222; }}
                .active {{ opacity: 1; color: #2196F3; border-left: 3px solid #2196F3; background: #111; }}
                #speed {{ position: fixed; top: 10px; left: 10px; background: rgba(0,0,0,0.5); padding: 5px; font-size: 12px; z-index: 10; }}
            </style>
        </head>
        <body>
            {f'<div id="speed">倍速: 1.0x</div>' if is_video else ''}
            <div id="viewer">
                {"<video autoplay controls src='" + media_src + "'></video>" if is_video else "<img src='" + media_src + "'>"}
            </div>
            <div id="sidebar"><div id="list"></div></div>
            <script>
                const token = "{token}";
                fetch('/list?token='+token).then(r=>r.json()).then(data=>{{
                    const box = document.getElementById('list');
                    data.forEach((item, i) => {{
                        const el = document.createElement('div');
                        el.className = 'item' + (i == {idx} ? ' active' : '');
                        el.innerText = (i+1) + '. ' + item.name;
                        el.onclick = () => {{
                            const v = document.querySelector('video');
                            if(v) {{ v.pause(); v.src = ""; v.load(); }}
                            location.href = `/view?token=${{token}}&idx=${{i}}&_t=${{Date.now()}}`;
                        }};
                        box.appendChild(el);
                    }});
                }});

                const v = document.querySelector('video');
                if(v) {{
                    window.onkeydown = (e) => {{
                        if(e.key === ']') v.playbackRate += 0.25;
                        if(e.key === '[') v.playbackRate -= 0.25;
                        if(e.key === ' ') {{ e.preventDefault(); v.paused?v.play():v.pause(); }}
                        document.getElementById('speed').innerText = "倍速: " + v.playbackRate.toFixed(2) + "x";
                    }};
                }}
            </script>
        </body>
        </html>
        """
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))

    def handle_raw_stream(self, path):
        try:
            size = os.path.getsize(path) - HEADER_SIZE
            with open(path, 'rb') as f:
                header = crypt_data(f.read(HEADER_SIZE))
                ext = header.decode('utf-8', errors='ignore').strip('\x00').lower()
                mime = 'video/mp4' if ext in ['.mp4', '.webm', '.mov'] else 'image/jpeg'

                range_h = self.headers.get('Range', 'bytes=0-')
                start = int(re.search(r'bytes=(\d+)-', range_h).group(1))
                end = size - 1

                self.send_response(206 if 'Range' in self.headers else 200)
                self.send_header('Content-type', mime)
                self.send_header('Accept-Ranges', 'bytes')
                self.send_header('Content-Length', str(size - start))
                self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
                self.end_headers()

                f.seek(HEADER_SIZE + start)
                while True:
                    chunk = f.read(CHUNK_SIZE)
                    if not chunk: break
                    try:
                        self.wfile.write(crypt_data(chunk))
                    except:
                        break
        except:
            pass

    def log_message(self, *args):
        pass


def run_webview_player(file_path, playlist):
    auth_token = secrets.token_urlsafe(16)
    server = ThreadedHTTPServer(('127.0.0.1', 0), DecryptServer)
    server.auth_token, server.encrypted_path, server.playlist = auth_token, file_path, playlist
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()

    start_idx = 0
    try:
        start_idx = playlist.index(file_path)
    except:
        pass

    url = f'http://127.0.0.1:{port}/stream?token={auth_token}&idx={start_idx}'
    webview.create_window(f"加密播放器", url=url, width=1100, height=700)
    webview.start()


class CryptoApp:
    def __init__(self, root):
        self.root = root
        # 1. 隐藏主窗口直到密码验证通过
        self.root.withdraw()
        if self.verify_password():
            self.root.deiconify()  # 显示主窗口
            self.root.title("加密中心")
            self.playlist = []
            self.current_process = None
            self.setup_ui()
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind('<<Drop>>', self.on_drop)
        else:
            self.root.destroy()

    def verify_password(self):
        # 硬编码口令
        SECRET_PASS = "eval271235"
        # 弹出输入框
        pwd = sd.askstring("身份验证", "请输入启动口令:", show='*')
        if pwd == SECRET_PASS:
            return True
        return False

    def setup_ui(self):
        self.root.geometry("600x450")
        main = tk.Frame(self.root)
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 修复：添加滚动条容器和滚动条
        list_frame = tk.Frame(main)
        list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.scrollbar = tk.Scrollbar(list_frame)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.listbox = tk.Listbox(list_frame, font=("微软雅黑", 10), yscrollcommand=self.scrollbar.set)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.config(command=self.listbox.yview)

        self.listbox.bind('<Double-1>', lambda e: self.play_action("switch"))

        btns = tk.Frame(main)
        btns.pack(side=tk.RIGHT, fill=tk.Y, padx=10)
        tk.Label(btns, text="支持拖入文件/文件夹", fg="gray", font=("", 9)).pack(pady=5)
        tk.Button(btns, text="播放 (当前窗口)", command=lambda: self.play_action("switch"), width=15).pack(pady=5)
        tk.Button(btns, text="播放 (新窗口)", command=lambda: self.play_action("new"), width=15).pack(pady=5)
        tk.Button(btns, text="清空列表", command=self.clear_list, width=15).pack(side=tk.BOTTOM)

    def on_drop(self, event):
        paths = self.root.tk.splitlist(event.data)
        for path in paths:
            path = path.strip('"')
            if os.path.isdir(path):
                self.process_directory(path)
            elif os.path.isfile(path):
                self.process_single_file(path)

    def process_directory(self, dir_path):
        """扫描并加密文件夹内容"""
        parent_dir = os.path.dirname(dir_path)
        folder_name = os.path.basename(dir_path)
        target_root = os.path.join(parent_dir, f"{folder_name}-sm")

        # 只有在确实需要加密文件时才创建目标根目录
        for root_dir, dirs, files in os.walk(dir_path):
            rel_path = os.path.relpath(root_dir, dir_path)
            for f in files:
                src_file = os.path.join(root_dir, f)
                ext = os.path.splitext(f)[1].lower()

                # 加密文件直接追加到列表
                if ext == TARGET_EXT:
                    self.add_to_list(src_file)
                elif ext in MEDIA_EXTS:
                    # 确保目标目录结构存在
                    dest_dir = os.path.join(target_root, rel_path)
                    if not os.path.exists(dest_dir):
                        os.makedirs(dest_dir, exist_ok=True)

                    tar_file = os.path.join(dest_dir, os.path.splitext(f)[0] + TARGET_EXT)
                    res = self.encrypt_file(src_file, tar_file)
                    if res: self.add_to_list(res)

    def process_single_file(self, path):
        ext = os.path.splitext(path)[1].lower()
        if ext == TARGET_EXT:
            self.add_to_list(path)
        elif ext in MEDIA_EXTS:
            tar = os.path.splitext(path)[0] + TARGET_EXT
            res = self.encrypt_file(path, tar)
            if res: self.add_to_list(res)

    def encrypt_file(self, src, tar):
        if os.path.exists(tar): return tar
        try:
            head = os.path.splitext(src)[1].encode().ljust(HEADER_SIZE, b'\x00')
            with open(src, 'rb') as fi, open(tar, 'wb') as fo:
                fo.write(crypt_data(head))
                while (c := fi.read(CHUNK_SIZE)):
                    fo.write(crypt_data(c))
            return tar
        except Exception as e:
            print(f"加密失败: {src} -> {e}")
            return None

    def add_to_list(self, path):
        if path not in self.playlist:
            self.playlist.append(path)
            self.listbox.insert(tk.END, os.path.basename(path))
            # 自动滚动到底部以显示最新添加的文件
            self.listbox.see(tk.END)

    def play_action(self, mode):
        sel = self.listbox.curselection()
        if not sel: return
        if mode == "switch" and self.current_process and self.current_process.is_alive():
            self.current_process.terminate()
        p = multiprocessing.Process(target=run_webview_player, args=(self.playlist[sel[0]], list(self.playlist)))
        p.daemon = True
        p.start()
        if mode == "switch": self.current_process = p

    def clear_list(self):
        self.playlist.clear()
        self.listbox.delete(0, tk.END)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    root = TkinterDnD.Tk()
    app = CryptoApp(root)
    root.mainloop()