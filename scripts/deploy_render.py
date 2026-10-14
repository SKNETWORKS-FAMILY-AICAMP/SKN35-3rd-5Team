"""Render 무료 배포를 명령 한 줄로 다시 실행한다 (GitHub 자동 배포 권한이 없을 때).

준비: Render → 서비스 → Settings → Deploy Hook 주소를 .env 에 넣는다 (주소는 비밀, 저장소에 올리지 않음)
    RENDER_DEPLOY_HOOK_API=https://api.render.com/deploy/srv-...
    RENDER_DEPLOY_HOOK_APP=https://api.render.com/deploy/srv-...

실행 (저장소 루트):
    uv run python scripts/deploy_render.py          # API + 화면 둘 다
    uv run python scripts/deploy_render.py api      # API 만

Render 는 main 브랜치의 최신 커밋을 배포하므로, 먼저 main 에 반영(push)한 뒤 실행한다.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
SERVICES = {
    "api": ("RENDER_DEPLOY_HOOK_API", "https://beaurette-api.onrender.com/health"),
    "app": ("RENDER_DEPLOY_HOOK_APP", "https://beaurette-app.onrender.com/"),
}


def _main_is_pushed() -> bool:
    """로컬 main 과 GitHub main 이 같은지 (다르면 Render 에 반영 안 된 코드가 있다는 뜻)."""
    try:
        subprocess.run(["git", "fetch", "-q", "origin", "main"], cwd=ROOT, check=True)
        remote = subprocess.run(["git", "log", "-1", "--format=%h %s", "origin/main"], cwd=ROOT,
                                capture_output=True, text=True, encoding="utf-8", check=True).stdout.strip()
        print(f"Render 가 배포할 커밋 (GitHub main): {remote}")
        return True
    except Exception as error:  # noqa: BLE001 - git 이 없어도 배포는 진행
        print(f"(GitHub main 확인 생략: {error})")
        return False


def main() -> int:
    load_dotenv(ROOT / ".env")
    targets = sys.argv[1:] or list(SERVICES)
    _main_is_pushed()

    triggered = []
    for name in targets:
        env_key, _ = SERVICES[name]
        hook = os.getenv(env_key, "").strip()
        if not hook:
            print(f"❌ {name}: .env 에 {env_key} 가 없습니다")
            continue
        res = httpx.post(hook, timeout=30)
        if res.status_code < 300:
            print(f"🚀 {name}: 배포 시작 (Render 가 설치·재시작에 3~5분 걸립니다)")
            triggered.append(name)
        else:
            print(f"❌ {name}: 배포 요청 실패 (HTTP {res.status_code}) - 훅 주소를 확인하세요")

    if not triggered:
        return 1
    print("\n상태 확인 중... (Ctrl+C 로 그만 기다려도 배포는 계속됩니다)")
    time.sleep(60)
    for _ in range(20):
        states = {}
        for name in triggered:
            try:
                states[name] = httpx.get(SERVICES[name][1], timeout=60).status_code == 200
            except httpx.HTTPError:
                states[name] = False
        print("  " + " · ".join(f"{n}: {'응답 중 ✅' if ok else '준비 중…'}" for n, ok in states.items()))
        if all(states.values()):
            print("\n완료. 새 버전이 뜨기까지 1~2분 더 걸릴 수 있으니 Render 대시보드 Events 에서 Live 를 확인하세요.")
            return 0
        time.sleep(20)
    print("\n아직 준비 중입니다. Render 대시보드에서 Logs 를 확인하세요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
