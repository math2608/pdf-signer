#!/usr/bin/env python3
"""PDF Digital Signer — assinar PDFs com certificado do Keychain."""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import os
import re
import json
import threading
import tempfile

CONFIG_PATH = os.path.expanduser("~/.pdf_signer_prefs.json")


# ─── Keychain helpers ─────────────────────────────────────────────────────────

def list_keychain_identities():
    try:
        result = subprocess.run(["security", "find-identity"],
                                capture_output=True, text=True)
        certs = []
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if not line or not line[0].isdigit() or '"' not in line:
                continue
            parts = line.split(None, 2)
            if len(parts) < 3:
                continue
            h, name = parts[1], parts[2].split('"')[1] if '"' in parts[2] else ""
            if len(h) == 40 and name:
                certs.append((h, name))
        return certs
    except Exception:
        return []


def extract_identity_pkcs12(all_p12_path, target_name):
    """Return single-identity PKCS12 bytes for target_name, or None."""
    result = subprocess.run(
        ["openssl", "pkcs12", "-in", all_p12_path,
         "-passin", "pass:", "-passout", "pass:", "-nodes"],
        capture_output=True
    )
    pem_text = result.stdout.decode("utf-8", errors="ignore")
    bags = re.split(r"(?=Bag Attributes)", pem_text)

    identities = {}
    for bag in bags:
        if not bag.strip():
            continue
        fn = re.search(r"friendlyName:\s*(.+)", bag)
        lki = re.search(r"localKeyID:\s*([0-9A-Fa-f ]+)", bag)
        name = fn.group(1).strip() if fn else ""
        key_id = lki.group(1).strip().replace(" ", "").lower() if lki else "__nokey__"
        if key_id not in identities:
            identities[key_id] = {"name": name, "cert": None, "key": None}
        cert_m = re.search(r"(-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----)", bag, re.DOTALL)
        key_m = re.search(r"(-----BEGIN (?:PRIVATE|RSA PRIVATE|EC PRIVATE) KEY-----.*?-----END (?:PRIVATE|RSA PRIVATE|EC PRIVATE) KEY-----)", bag, re.DOTALL)
        if cert_m:
            identities[key_id]["cert"] = cert_m.group(1)
            if name:
                identities[key_id]["name"] = name
        if key_m:
            identities[key_id]["key"] = key_m.group(1)

    target_lower = target_name.lower()
    match = next((d for d in identities.values()
                  if d["cert"] and d["key"] and
                  (target_lower in d["name"].lower() or d["name"].lower() in target_lower)),
                 None)
    if not match:
        return None

    cert_tmp = key_tmp = out_tmp = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pem", delete=False, mode="w") as f:
            f.write(match["cert"]); cert_tmp = f.name
        with tempfile.NamedTemporaryFile(suffix=".pem", delete=False, mode="w") as f:
            f.write(match["key"]); key_tmp = f.name
        with tempfile.NamedTemporaryFile(suffix=".p12", delete=False) as f:
            out_tmp = f.name
        subprocess.run(["openssl", "pkcs12", "-export",
                        "-in", cert_tmp, "-inkey", key_tmp,
                        "-out", out_tmp, "-passout", "pass:"],
                       check=True, capture_output=True)
        with open(out_tmp, "rb") as f:
            return f.read()
    finally:
        for t in [cert_tmp, key_tmp, out_tmp]:
            if t and os.path.exists(t):
                os.unlink(t)


# ─── Config ───────────────────────────────────────────────────────────────────

def load_config():
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(data):
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(data, f)
    except Exception:
        pass


# ─── PDF Preview + Sign Window ────────────────────────────────────────────────

class SignWindow(tk.Toplevel):
    CANVAS_W = 650
    CANVAS_H = 820

    def __init__(self, parent, pdf_path, cert_name, on_done):
        super().__init__(parent)
        self.title(f"Assinar — {os.path.basename(pdf_path)}")
        self.resizable(False, False)
        self.pdf_path = pdf_path
        self.cert_name = cert_name
        self.on_done = on_done  # callback(success, output_path)

        self.doc = None
        self.page_count = 1
        self.current_page = 0
        self.scale = 1.0
        self.pdf_w = self.pdf_h = 0
        self.render_w = self.render_h = 0
        self._tk_img = None
        self.rect_start = None
        self.rect_id = None          # current drawing rect
        self.rect_ids = []           # all committed rects on canvas
        self._boxes = []             # list of (page, x1, y1, x2, y2)

        self._load_doc()
        self._build_ui()
        self._render_page()
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _load_doc(self):
        import fitz
        self.doc = fitz.open(self.pdf_path)
        self.page_count = len(self.doc)

    def _build_ui(self):
        # ── Nav bar ──
        nav = ttk.Frame(self, padding=(8, 4))
        nav.pack(fill="x")
        ttk.Button(nav, text="◀", width=3, command=self._prev).pack(side="left")
        self.page_lbl = ttk.Label(nav, text="")
        self.page_lbl.pack(side="left", padx=8)
        ttk.Button(nav, text="▶", width=3, command=self._next).pack(side="left")
        ttk.Label(nav, text="  Arraste para adicionar áreas de assinatura",
                  foreground="gray").pack(side="left", padx=10)
        ttk.Button(nav, text="🗑 Limpar", command=self._clear_boxes).pack(side="right", padx=4)

        # ── Canvas ──
        self.canvas = tk.Canvas(self, bg="#666", cursor="crosshair")
        self.canvas.pack(padx=8, pady=(0, 4))
        self.canvas.bind("<ButtonPress-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        # Scroll to navigate pages
        self.canvas.bind("<MouseWheel>", self._scroll)        # macOS/Windows
        self.canvas.bind("<Button-4>", self._scroll)          # Linux scroll up
        self.canvas.bind("<Button-5>", self._scroll)          # Linux scroll down

        # ── Bottom bar ──
        bot = ttk.Frame(self, padding=(8, 4))
        bot.pack(fill="x")
        self.cert_lbl = ttk.Label(bot, text=f"🔑 {self.cert_name}",
                                  foreground="#1a6b1a")
        self.cert_lbl.pack(side="left")
        ttk.Button(bot, text="Cancelar", command=self.destroy).pack(side="right", padx=(4, 0))
        self.sign_btn = ttk.Button(bot, text="✍  Assinar PDF", command=self._sign)
        self.sign_btn.pack(side="right")
        self.box_lbl = ttk.Label(bot, text="Desenhe as áreas de assinatura",
                                 foreground="gray")
        self.box_lbl.pack(side="right", padx=(0, 12))

    def _render_page(self):
        import fitz
        from PIL import Image, ImageTk
        page = self.doc[self.current_page]
        pw, ph = page.rect.width, page.rect.height
        sx = self.CANVAS_W / pw
        sy = self.CANVAS_H / ph
        self.scale = min(sx, sy)
        self.render_w = int(pw * self.scale)
        self.render_h = int(ph * self.scale)
        self.pdf_w, self.pdf_h = pw, ph
        mat = fitz.Matrix(self.scale, self.scale)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        self._tk_img = ImageTk.PhotoImage(img)
        self.canvas.config(width=self.render_w, height=self.render_h)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self._tk_img)
        self.rect_id = None
        self.rect_ids = []
        self.page_lbl.config(text=f"Página {self.current_page + 1} / {self.page_count}")
        # Redraw existing boxes for this page
        for i, (pg, x1, y1, x2, y2) in enumerate(self._boxes):
            if pg == self.current_page:
                cx1 = int(x1 * self.scale)
                cy1 = int((self.pdf_h - y2) * self.scale)
                cx2 = int(x2 * self.scale)
                cy2 = int((self.pdf_h - y1) * self.scale)
                rid = self.canvas.create_rectangle(
                    cx1, cy1, cx2, cy2,
                    outline="#e53935", width=2, fill="#ffcccc", stipple="gray25"
                )
                self.canvas.create_text(
                    cx1 + 6, cy1 + 6, text=str(i + 1),
                    fill="#e53935", font=("Helvetica", 10, "bold"), anchor="nw"
                )
                self.rect_ids.append(rid)
        self._update_box_lbl()

    def _prev(self):
        if self.current_page > 0:
            self.current_page -= 1
            self._render_page()

    def _next(self):
        if self.current_page < self.page_count - 1:
            self.current_page += 1
            self._render_page()

    def _clear_boxes(self):
        self._boxes.clear()
        self._render_page()

    def _update_box_lbl(self):
        n = len(self._boxes)
        if n == 0:
            self.box_lbl.config(text="Desenhe as áreas de assinatura", foreground="gray")
        else:
            self.box_lbl.config(text=f"{n} área(s) desenhada(s)", foreground="#1a6b1a")

    def _scroll(self, e):
        # e.delta: positive = scroll up (prev page), negative = scroll down (next page)
        # Button-4/5 for Linux
        delta = e.delta if hasattr(e, "delta") and e.delta != 0 else (1 if e.num == 4 else -1)
        if delta > 0:
            self._prev()
        else:
            self._next()

    def _press(self, e):
        self.rect_start = (e.x, e.y)
        if self.rect_id:
            self.canvas.delete(self.rect_id)
            self.rect_id = None

    def _drag(self, e):
        if not self.rect_start:
            return
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        x0, y0 = self.rect_start
        self.rect_id = self.canvas.create_rectangle(
            x0, y0, e.x, e.y,
            outline="#e53935", width=2, fill="#ffcccc", stipple="gray25"
        )

    def _release(self, e):
        if not self.rect_start:
            return
        x0, y0 = self.rect_start
        x1, y1 = e.x, e.y
        cx1, cx2 = sorted([x0, x1])
        cy1, cy2 = sorted([y0, y1])
        if abs(cx2 - cx1) < 5 or abs(cy2 - cy1) < 5:
            if self.rect_id:
                self.canvas.delete(self.rect_id)
                self.rect_id = None
            return
        # Convert to PDF coords (flip Y, PDF origin = bottom-left)
        px1 = round(cx1 / self.scale)
        px2 = round(cx2 / self.scale)
        py1 = round(self.pdf_h - cy2 / self.scale)
        py2 = round(self.pdf_h - cy1 / self.scale)
        self._boxes.append((self.current_page, px1, py1, px2, py2))
        # Add number label on the committed rect
        n = len(self._boxes)
        self.canvas.create_text(
            cx1 + 6, cy1 + 6, text=str(n),
            fill="#e53935", font=("Helvetica", 10, "bold"), anchor="nw"
        )
        self.rect_id = None
        self._update_box_lbl()

    def _sign(self):
        if not self._boxes:
            messagebox.showwarning("Atenção", "Desenhe ao menos uma área de assinatura.", parent=self)
            return
        self.sign_btn.config(state="disabled")
        self.box_lbl.config(text="Assinando…", foreground="gray")
        threading.Thread(target=self._do_sign, daemon=True).start()

    def _do_sign(self):
        try:
            from pyhanko.sign import signers
            from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
            from pyhanko.sign.fields import SigFieldSpec
            from pyhanko.stamp import TextStampStyle
            from pyhanko.sign.signers.pdf_signer import PdfSigner

            import time, io

            # Export cert once, reuse for all signatures
            with tempfile.NamedTemporaryFile(suffix=".p12", delete=False) as tmp:
                all_p12 = tmp.name
            try:
                subprocess.run(
                    ["security", "export",
                     "-k", os.path.expanduser("~/Library/Keychains/login.keychain-db"),
                     "-t", "identities", "-f", "pkcs12", "-P", "", "-o", all_p12],
                    check=True, capture_output=True
                )
                filtered = extract_identity_pkcs12(all_p12, self.cert_name)
                if not filtered:
                    raise ValueError(f"Certificado '{self.cert_name}' não encontrado.")
            finally:
                if os.path.exists(all_p12):
                    os.unlink(all_p12)

            with tempfile.NamedTemporaryFile(suffix=".p12", delete=False) as tmp:
                tmp.write(filtered)
                filtered_path = tmp.name
            try:
                signer = signers.SimpleSigner.load_pkcs12(
                    pfx_file=filtered_path, passphrase=None)
            finally:
                if os.path.exists(filtered_path):
                    os.unlink(filtered_path)

            stamp = TextStampStyle(
                stamp_text="Assinado digitalmente por:\n%(signer)s\n\n%(ts)s",
                background_opacity=0,
            )

            # Sign each box incrementally (output of each becomes input of next)
            base, ext = os.path.splitext(self.pdf_path)
            output = f"{base}_assinado{ext}"
            with open(self.pdf_path, "rb") as f:
                current_pdf = io.BytesIO(f.read())

            for i, (page, x1, y1, x2, y2) in enumerate(self._boxes):
                field_name = f"Assinatura_{int(time.time())}_{i}"
                pdf_signer = PdfSigner(
                    signers.PdfSignatureMetadata(field_name=field_name),
                    signer=signer,
                    stamp_style=stamp,
                    new_field_spec=SigFieldSpec(
                        sig_field_name=field_name,
                        on_page=page,
                        box=(x1, y1, x2, y2)
                    )
                )
                current_pdf.seek(0)
                writer = IncrementalPdfFileWriter(current_pdf)
                out = pdf_signer.sign_pdf(writer)
                current_pdf = io.BytesIO(out.read())

            with open(output, "wb") as f:
                current_pdf.seek(0)
                f.write(current_pdf.read())

            self.after(0, lambda: self._success(output))

        except Exception as e:
            err = str(e)
            self.after(0, lambda: self._error(err))

    def _success(self, output):
        messagebox.showinfo("Sucesso", f"PDF assinado!\n\nSalvo em:\n{output}", parent=self)
        subprocess.run(["open", "-R", output])
        self.on_done(True, output)
        self.destroy()

    def _error(self, msg):
        self.sign_btn.config(state="normal")
        self.box_lbl.config(text="Erro ao assinar", foreground="red")
        messagebox.showerror("Erro ao assinar", msg, parent=self)


# ─── Main Window ──────────────────────────────────────────────────────────────

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Assinar PDF")
        self.root.resizable(False, False)
        w, h = 480, 250
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

        self.config = load_config()
        self.certs = []
        self.selected_cert = tk.StringVar()
        self.status_var = tk.StringVar(value="Pronto.")

        self._build_ui()
        self._load_certs()

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=24)
        main.pack(fill="both", expand=True)

        tk.Label(main, text="Assinar PDF", font=("Helvetica", 17, "bold")).pack(anchor="w")
        tk.Label(main, text="Assine documentos com seu certificado digital",
                 foreground="gray").pack(anchor="w", pady=(2, 16))

        # ── Certificado ──
        cert_row = ttk.Frame(main)
        cert_row.pack(fill="x")
        ttk.Label(cert_row, text="Certificado:", width=12).pack(side="left")
        self.cert_combo = ttk.Combobox(cert_row, textvariable=self.selected_cert,
                                       state="readonly", width=28)
        self.cert_combo.pack(side="left")
        ttk.Button(cert_row, text="↺", width=3,
                   command=self._load_certs).pack(side="left", padx=(4, 0))

        # ── Padrão ──
        default_row = ttk.Frame(main)
        default_row.pack(fill="x", pady=(4, 0))
        ttk.Label(default_row, text="", width=12).pack(side="left")
        ttk.Button(default_row, text="★ Definir como padrão",
                   command=self._set_default).pack(side="left")

        lbl_row = ttk.Frame(main)
        lbl_row.pack(fill="x")
        ttk.Label(lbl_row, text="", width=12).pack(side="left")
        self.default_lbl = ttk.Label(lbl_row, text="", foreground="gray")
        self.default_lbl.pack(side="left")

        # ── Abrir PDF ──
        ttk.Button(main, text="📄  Selecionar PDF para assinar",
                   command=self._open_pdf).pack(pady=(20, 0))

        # ── Status ──
        ttk.Separator(self.root).pack(fill="x", side="bottom", pady=(0, 22))
        ttk.Label(self.root, textvariable=self.status_var,
                  foreground="gray").pack(side="bottom", pady=(0, 6))

    def _load_certs(self):
        self.status_var.set("Carregando certificados…")
        self.certs = list_keychain_identities()
        if not self.certs:
            messagebox.showinfo(
                "Nenhum certificado",
                "Nenhum certificado com chave privada encontrado no Keychain.\n\n"
                "Abra o Keychain Access e verifique seus certificados em 'Meus Certificados'."
            )
            self.status_var.set("Nenhum certificado encontrado.")
            return

        names = [n for _, n in self.certs]
        self.cert_combo["values"] = names

        # Restore default if saved
        default = self.config.get("default_cert")
        if default and default in names:
            self.selected_cert.set(default)
            self.default_lbl.config(text=f"Padrão: {default[:40]}…" if len(default) > 40 else f"Padrão: {default}")
        else:
            self.cert_combo.current(0)

        self.status_var.set(f"{len(names)} certificado(s) encontrado(s).")

    def _set_default(self):
        cert = self.selected_cert.get()
        if not cert:
            return
        self.config["default_cert"] = cert
        save_config(self.config)
        label = f"Padrão: {cert[:40]}…" if len(cert) > 40 else f"Padrão: {cert}"
        self.default_lbl.config(text=label)
        self.status_var.set("Certificado padrão salvo.")

    def _open_pdf(self):
        cert = self.selected_cert.get()
        if not cert:
            messagebox.showerror("Erro", "Selecione um certificado primeiro.")
            return

        try:
            import fitz
            from PIL import Image, ImageTk
        except ImportError as e:
            messagebox.showerror("Dependência faltando",
                                 f"Instale: pip install pymupdf pillow\n\n{e}")
            return

        path = filedialog.askopenfilename(
            title="Selecionar PDF",
            filetypes=[("PDF", "*.pdf")]
        )
        if not path:
            return

        self.status_var.set(f"Abrindo {os.path.basename(path)}…")
        SignWindow(self.root, path, cert, self._on_signed)

    def _on_signed(self, success, output):
        if success:
            self.status_var.set(f"✓ Assinado: {os.path.basename(output)}")
        else:
            self.status_var.set("Assinatura cancelada.")


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
