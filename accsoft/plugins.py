"""افزونه‌ها: پوشهٔ <داده>/plugins/<id>/ شامل manifest.json و اختیاری plugin.py (تابع register(api)) و static/.
هر افزونه می‌تواند با فیلد "product" به یک محصول لایسنس‌دار در کاتالوگ وصل شود؛ بدون لایسنس معتبر اجرا نمی‌شود.
هشدار: کد افزونه با همهٔ دسترسی‌های برنامه اجرا می‌شود؛ فقط افزونهٔ معتبر و قابل‌اعتماد نصب کنید."""
import importlib.util
import json
import re

from . import access, licensing
from .config import data_dir

ID_RX = re.compile(r"^[a-z0-9_-]{2,40}$")


class PluginAPI:
    def __init__(self, app, pid):
        self.app, self.id, self.db = app, pid, app.db

    def route(self, method, pattern, perm="any"):
        """ثبت مسیر زیر /api/plugins/<id>/... ؛ perm یکی از کلیدهای access.PERMS یا any."""
        full = f"/api/plugins/{self.id}{pattern}"
        access.add_rule(method, full, perm)

        def deco(fn):
            self.app.route(method, full)(fn)
            return fn
        return deco

    def get(self, key, default=None):
        return self.db.get(f"plugin.{self.id}.{key}", default)

    def set(self, key, value):
        self.db.set(f"plugin.{self.id}.{key}", value)


class PluginManager:
    def __init__(self, app):
        self.app, self.manifests, self.loaded, self.errors = app, {}, set(), {}
        self.scan()
        self.reload()

    def scan(self):
        root = data_dir() / "plugins"
        self.manifests = {}
        if not root.is_dir():
            return
        for d in sorted(root.iterdir()):
            try:
                m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
                if not ID_RX.match(m["id"]) or m["id"] != d.name:
                    raise ValueError("id نامعتبر یا ناهمخوان با نام پوشه")
                m["_dir"] = d
                self.manifests[m["id"]] = m
            except Exception as e:
                self.errors[d.name] = f"manifest نامعتبر: {e}"

    def entitled(self, pid):
        m = self.manifests.get(pid)
        if not m:
            return False
        prod = m.get("product")
        return not prod or prod in licensing.entitlements(self.app.db)

    def reload(self):
        """افزونه‌های مجازِ هنوز بارگذاری‌نشده را بارگذاری می‌کند (پس از فعال‌سازی لایسنس صدا زده می‌شود)."""
        for pid, m in self.manifests.items():
            if pid in self.loaded or not self.entitled(pid):
                continue
            entry = m.get("entry")
            if entry:
                try:
                    if not re.fullmatch(r"[A-Za-z0-9_.-]+\.py", entry):
                        raise ValueError("نام فایل ورودی نامعتبر")
                    spec = importlib.util.spec_from_file_location(f"accsoft_plugin_{pid}", m["_dir"] / entry)
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    mod.register(PluginAPI(self.app, pid))
                except Exception as e:
                    self.errors[pid] = f"خطا در بارگذاری: {e}"
                    continue
            if m.get("menu") and m["menu"].get("page"):
                access.add_rule("GET", f"/plugin/{pid}/[A-Za-z0-9_.-]+", m.get("perm", "any"))
            self.loaded.add(pid)

    def listing(self, role_perms):
        out = []
        for pid, m in self.manifests.items():
            lic = self.entitled(pid)
            perm = m.get("perm", "any")
            out.append({"id": pid, "name": m.get("name", pid), "version": m.get("version", ""), "product": m.get("product"),
                        "licensed": lic, "loaded": pid in self.loaded, "error": self.errors.get(pid),
                        "menu": (m.get("menu") if lic and pid in self.loaded and (perm == "any" or perm in role_perms) else None)})
        return out

    def static_file(self, pid, name):
        m = self.manifests.get(pid)
        if not m or not self.entitled(pid) or not re.fullmatch(r"[A-Za-z0-9_.-]+", name):
            return None
        f = m["_dir"] / "static" / name
        return f if f.is_file() else None
