"""매일 한 번 실행: 모든 출처에서 공고를 모아 docs/notices.json 을 갱신하고, 새 공고를 텔레그램으로 알린다."""
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote

import requests

sys.path.insert(0, str(Path(__file__).parent))
from sources import SOURCES  # noqa: E402
from util import KST, today_kst  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "docs" / "notices.json"
KEEP_DAYS = 60          # 게시 후 이만큼 지났고 마감도 지난 공고는 목록에서 뺀다
CAT_NAME = {"sale": "분양", "pub": "공공임대", "pri": "민간임대", "rem": "무순위·잔여", "news": "뉴스"}


def load_previous() -> dict:
    if OUT.exists():
        try:
            return json.loads(OUT.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"items": [], "sources": []}


def redact(text: str) -> str:
    """오류 문구에 섞인 인증키를 지운다 (notices.json 은 공개 저장소에 올라가므로)."""
    text = re.sub(r"(?i)(service_?key|client_?secret|client_?id|token)=[^&\s'\"]+", r"\1=***", text)
    for name in ("DATA_GO_KR_KEY", "NAVER_CLIENT_ID", "NAVER_CLIENT_SECRET", "TELEGRAM_BOT_TOKEN"):
        secret = os.environ.get(name)
        if secret and len(secret) > 4:
            text = text.replace(secret, "***").replace(quote(secret, safe=""), "***")
    return text


def run_sources(only=None):
    session = requests.Session()
    items, status = [], []
    for name, fn in SOURCES:
        if only and name not in only:
            continue
        try:
            got = fn(session)
            items += got
            status.append({"name": name, "ok": True, "count": len(got)})
            print(f"[ok]   {name}: {len(got)}건")
        except Exception as e:  # 한 곳이 실패해도 나머지는 계속
            msg = redact(f"{type(e).__name__}: {e}" if not str(e).startswith("SKIP") else str(e))
            skipped = msg.startswith("SKIP")
            status.append({"name": name, "ok": False, "skipped": skipped, "error": msg[:200]})
            print(f"[{'skip' if skipped else 'fail'}] {name}: {msg[:300]}")
    return items, status


def merge(prev: dict, fresh: list, status: list, now: str):
    today = today_kst()
    old = {n["id"]: n for n in prev.get("items", [])}
    failed_sources = {s["name"] for s in status if not s["ok"]}
    seen_ids, merged, new = set(), [], []

    for n in fresh:
        if n["id"] in seen_ids:
            continue
        seen_ids.add(n["id"])
        if n["id"] in old:
            n["first_seen"] = old[n["id"]].get("first_seen", now)
        else:
            n["first_seen"] = now
            new.append(n)
        merged.append(n)

    # 이번에 실패한 출처의 공고는 지난번 것을 그대로 남겨 둔다
    src_of = {"청약홈": "청약홈", "LH": "LH 공고", "SH": "SH 공고", "청년안심주택": "청년안심주택",
              "롯데 엘리스": "롯데 엘리스", "뉴스": "네이버 뉴스"}
    for n in old.values():
        if n["id"] in seen_ids:
            continue
        src_name = src_of.get(n["source"], n["source"])
        if any(f.startswith(src_name) for f in failed_sources):
            merged.append(n)

    cutoff = (today - timedelta(days=KEEP_DAYS)).isoformat()
    week_ago = (today - timedelta(days=7)).isoformat()
    merged = [n for n in merged if (n.get("end") or "9999") >= week_ago or (n.get("posted") or "") >= cutoff]
    merged.sort(key=lambda n: (n.get("posted") or "", n.get("first_seen", "")), reverse=True)
    return merged, new


def notify(new: list, is_first_run: bool):
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat) or not new:
        return
    if is_first_run:
        text = f"공고 알림을 시작했어요. 지금 올라와 있는 공고 {len(new)}건을 모았어요."
    else:
        lines = [f"새 공고 {len(new)}건"]
        for n in new[:25]:
            when = f" · 마감 {n['end'][5:].replace('-', '/')}" if n.get("end") else ""
            lines.append(f"• [{CAT_NAME.get(n['cat'], '')}] {n['region']} {n['title']}{when}")
        if len(new) > 25:
            lines.append(f"…외 {len(new) - 25}건")
        site = os.environ.get("SITE_URL")
        if site:
            lines.append(site)
        text = "\n".join(lines)
    try:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      data={"chat_id": chat, "text": text, "disable_web_page_preview": True}, timeout=20)
    except Exception as e:
        print("텔레그램 전송 실패:", e)


def main():
    only = sys.argv[1:] or None
    prev = load_previous()
    now = datetime.now(KST).isoformat(timespec="minutes")
    fresh, status = run_sources(only)
    items, new = merge(prev, fresh, status, now)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"updated": now, "sources": status, "items": items},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"저장: {len(items)}건 (새 공고 {len(new)}건)")
    notify(new, is_first_run=not prev.get("updated"))


if __name__ == "__main__":
    main()
