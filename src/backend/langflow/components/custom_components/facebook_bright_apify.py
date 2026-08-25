# Exact operational custom-component source snapshot; keep legacy exception handling unchanged.
# ruff: noqa: ASYNC210, BLE001, E722, RUF012, S110
import asyncio
import json
import random
import traceback
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests
from apify_client import ApifyClient
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async

from langflow.components.custom_components.facebook_metrics import (
    extract_og_view_count,
    extract_provider_view_count,
    is_facebook_video,
    parse_view_count,
)
from langflow.custom import Component
from langflow.io import MessageTextInput, Output
from langflow.schema import Message


class CustomComponent(Component):
    display_name = "Facebook Bright Apify"
    icon = "code"
    name = "Facebook Bright Apify"

    inputs = [
        MessageTextInput(
            name="bright_api_key",
            display_name="Bright API key",
            value="",
            tool_mode=True,
        ),
        MessageTextInput(
            name="apify_api_key",
            display_name="Apify API key",
            value="",
            tool_mode=True,
        ),
        MessageTextInput(
            name="url",
            display_name="URL",
            value="",
            tool_mode=True,
        ),
        MessageTextInput(
            name="storage_state",
            display_name="Storage State",
            value="/link_volumes/fb_state.json",
            tool_mode=True,
        ),
        MessageTextInput(
            name="lastest_comment_id",
            display_name="lastest_comment_id",
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="Output", name="output", method="build_output"),
    ]

    checked_dismiss = False
    playwright_timeout = 3_000

    async def build_output(self) -> Message:
        # return json.dumps({"message": "파싱 실패"}, ensure_ascii=False)

        try:
            headers = {
                "Authorization": f"Bearer {self.bright_api_key}",
                "Content-Type": "application/json",
            }

            url = self.url.strip()
            api_url = "https://api.brightdata.com/datasets/v3/trigger"

            # 게시글 정보
            response = requests.post(
                api_url,
                headers=headers,
                params={
                    "dataset_id": "gd_lyclm1571iy3mv57zw",
                    "include_errors": "true",
                    "format": "json",
                },
                json=[
                    {"url": url},
                ],
            )
            if response.status_code != 200:
                print("Error:", response.status_code, response.text)
                _result = {
                    "message": f"게시글 정보를 가져오는데 실패했습니다.[A_{response.status_code}]\n{response.text}",
                }
                self.teams_message(_result["message"])
                return Message(text=json.dumps(_result, ensure_ascii=False))

            post_data = response.json()
            post_snapshot = post_data.get("snapshot_id")

            is_complete_post = not post_snapshot

            # 댓글 정보
            # response = requests.post(
            #     api_url,
            #     headers=headers,
            #     params={
            #         "dataset_id": "gd_lkay758p1eanlolqw8",
            #         "include_errors": "true",
            #         "format": "json",
            #     },
            #     json=[
            #         {"url": url},
            #     ],
            # )
            # if response.status_code != 200:
            #     print("Error:", response.status_code, response.text)
            #     _result = {
            #         "message": f"댓글 정보를 가져오는데 실패했습니다.[A_{response.status_code}]",
            #     }
            #     comment_data = []
            #     comment_snapshot = None
            # else:
            #     comment_data = response.json()
            #     comment_snapshot = comment_data.get("snapshot_id")

            # is_complete_comment = not comment_snapshot

            try_count = 0
            while not is_complete_post:
                # or not is_complete_comment:
                if try_count > 20:
                    _snapshot_str = "snapshot_id:"
                    if not is_complete_post:
                        _snapshot_str += f" post {post_snapshot}"
                    # if not is_complete_comment:
                    #     _snapshot_str += f" comment {comment_snapshot}"

                    _result = {
                        "message": f"스크래핑 정보를 가져오는데 실패했습니다.(재시도 초과)\nsnapshot:{_snapshot_str}\npost:{is_complete_post!s}",
                    }
                    self.teams_message(_result["message"])
                    if is_complete_post:
                        # is_complete_comment = True
                        # comment_data = []
                        pass
                    else:
                        return Message(text=json.dumps(_result, ensure_ascii=False))

                if not is_complete_post:
                    post_data = self.get_snapshot(post_snapshot)
                    if post_data and isinstance(post_data, list):
                        print("post_data", post_data)
                        is_complete_post = True
                    elif post_data and isinstance(post_data, dict) and "error" in post_data:
                        _result = {
                            "message": f"게시글 정보를 가져오는데 실패했습니다.({post_data.get('error', '')})",
                        }
                        self.teams_message(_result["message"])
                        return Message(text=json.dumps(_result, ensure_ascii=False))
                    elif post_data is None:
                        _result = {
                            "message": "게시글 정보를 가져오는데 실패했습니다.",
                        }
                        self.teams_message(_result["message"])
                        return Message(text=json.dumps(_result, ensure_ascii=False))

                # if not is_complete_comment:
                #     comment_data = self.get_snapshot(comment_snapshot)
                #     print("comment_data A", comment_data)
                #     if comment_data and isinstance(comment_data, list):
                #         print("comment_data", comment_data)
                #         is_complete_comment = True
                #     elif comment_data and isinstance(comment_data, dict) and "error" in comment_data:
                #         _result = {
                #             "message": f"댓글 정보를 가져오는데 실패했습니다.({comment_data.get("error", "")})",
                #         }
                #         self.teams_message(_result["message"])
                #         is_complete_comment = True
                #         comment_data = []
                #     elif comment_data is None:
                #         _result = {
                #             "message": "댓글 정보를 가져오는데 실패했습니다.",
                #         }
                #         self.teams_message(_result["message"])
                #         is_complete_comment = True
                #         comment_data = []

                try_count += 1
                await asyncio.sleep(30)

            if "error_code" in post_data[0]:
                message = f"게시글 정보를 가져오는데 실패했습니다.[{post_data[0]['error_code']}]"
                if post_data[0]["error_code"] == "dead_page":
                    message = f"삭제된 게시글입니다.[{post_data[0]['error_code']}]"
                _result = {
                    "message": message,
                }
                self.teams_message(message)
                return Message(text=json.dumps(_result, ensure_ascii=False))

            like_count = 0
            for like_data in post_data[0].get("num_likes_type", []):
                like_count += like_data.get("num") or 0

            # comments = []
            # for item in comment_data:
            #     if "comment_text" in item:
            #         comment = {
            #             "id": item.get("comment_id", ""),
            #             "name": item.get("user_name", ""),
            #             "content": item.get("comment_text", ""),
            #             "like_count": item.get("num_likes", 0),
            #             "published_at": self.utc_to_kst(item.get("date_created", "")),
            #         }
            #         comments.append(comment)

            comment_count = post_data[0].get("num_comments", 0) or 0
            req_comment_count = max(50000, comment_count)
            comments = []

            if comment_count > 0:
                # Apify 댓글 수집
                client = ApifyClient(self.apify_api_key)
                run_input = {
                    "startUrls": [{"url": self.url}],
                    "resultsLimit": 2000 if self.lastest_comment_id else req_comment_count,
                    "includeNestedComments": False,
                    "viewOption": "RECENT_ACTIVITY",
                }

                run = client.actor("us5srxAYnsrkgUv2v").call(run_input=run_input)
                _comments = client.dataset(run["defaultDatasetId"]).iterate_items()
                for item in _comments:
                    if not "text" in item:
                        continue
                    comment = {
                        "id": item["id"],
                        "name": item["profileName"],
                        "content": item["text"],
                        "like_count": item["likesCount"],
                        "published_at": self.utc_to_kst(item["date"]),
                    }
                    comments.append(comment)

            result = {
                "name": post_data[0].get("user_username_raw"),
                "content": post_data[0].get("content") or "",
                "like_count": like_count,
                "comment_count": post_data[0].get("num_comments", 0) or 0,
                "share_count": post_data[0].get("num_shares", 0) or 0,
                "published_at": self.utc_to_kst(post_data[0].get("date_posted")),
                "type": "B",
                "comments": comments,
            }

            view_count = extract_provider_view_count(post_data[0])
            if view_count is None and self._is_video_url_or_attachment(post_data[0]):
                view_count = await self.get_video_view_count()
            if view_count is not None:
                result["view_count"] = view_count

            # is_none_comment_count = result.get("comment_count") is None
            # is_none_share_count = result.get("share_count") is None

            # _view_count = None

            # if is_none_comment_count:
            #     (
            #         comment_count,
            #         share_count,
            #         _view_count,
            #     ) = await self.get_reels_comment_share_count(result["name"])

            #     if is_none_comment_count and comment_count is not None:
            #         result["comment_count"] = comment_count
            #     if is_none_share_count and share_count is not None:
            #         result["share_count"] = share_count
            #     if result.get("view_count") is None and _view_count is not None:
            #         result["view_count"] = _view_count

            # if result.get("view_count") is None:
            #     attachments = post_data[0].get("attachments", [])
            #     if attachments and attachments[0].get("type") == "video":
            #         if _view_count is None:
            #             (
            #                 comment_count,
            #                 share_count,
            #                 _view_count,
            #             ) = await self.get_reels_comment_share_count(result["name"])
            #         if _view_count is not None:
            #             result["view_count"] = _view_count

            return Message(text=json.dumps(result, ensure_ascii=False))
        except Exception:
            error_message = traceback.format_exc()
            _message = f"스크래핑 중 오류가 발생했습니다.\n{error_message}"
            self.teams_message(_message)

            return Message(text=json.dumps({"message": _message}, ensure_ascii=False))

    def get_snapshot(self, snapshot_id):
        bright_url = f"https://api.brightdata.com/datasets/v3/snapshot/{snapshot_id}"
        headers = {
            "Authorization": f"Bearer {self.bright_api_key}",
            "Content-Type": "application/json",
        }
        response = requests.get(bright_url, headers=headers, params={"format": "json"})
        if response.status_code >= 200 and response.status_code < 300:
            return response.json()
        elif "is empty" in response.text:
            return []
        else:
            print(f"Error: {response.status_code} - {response.text}")
            return {"error": {response.status_code} - {response.text}}

    def utc_to_kst(self, utc_str):
        utc_dt = datetime.strptime(utc_str, "%Y-%m-%dT%H:%M:%S.000Z").replace(tzinfo=timezone.utc)
        kst_offset = timedelta(hours=9)
        kst_dt = utc_dt + kst_offset
        return kst_dt.strftime("%Y-%m-%d %H:%M:%S")

    def timestamp_to_str(self, timestamp):
        dt_utc = datetime.fromtimestamp(int(timestamp), tz=timezone.utc)
        dt_kst = dt_utc.astimezone(ZoneInfo("Asia/Seoul"))
        return dt_kst.strftime("%Y-%m-%d %H:%M:%S%z")

    def parse_abbreviated_number(self, value: str | None) -> int | None:
        return parse_view_count(value)

    def _is_video_url_or_attachment(self, post: dict) -> bool:
        return is_facebook_video(self.url, post.get("attachments"))

    async def check_dismiss(self, page):
        if self.checked_dismiss:
            return True

        try:
            await page.click(
                "xpath=//*[@role='button' and @aria-label='Dismiss' and .//text()[normalize-space()='Dismiss']]",
                strict=False,
                timeout=3000,
            )
            await page.goto(self.url)
            self.checked_dismiss = True
            await page.wait_for_timeout(2_000)
            return True
        except:
            self.checked_dismiss = True
            return False

    async def start_playwirhgt(self):
        if not self._p:
            self._p = await async_playwright().start()

            if not self._browser:
                self._browser.close()

            self._browser = await self._p.chromium.launch(
                headless=True,
                args=[
                    "--disable-gpu",  # GPU 미사용
                    "--no-sandbox",  # 도커 등에서 필수
                    "--disable-dev-shm-usage",  # 메모리 공유 대신 디스크 사용
                    "--disable-setuid-sandbox",  # setuid 샌드박스 비활성화
                    "--disable-extensions",  # 확장 프로그램 제거
                    "--disable-sync",  # 계정 동기화 차단
                    "--disable-default-apps",  # 불필요한 앱 제거
                    "--disable-translate",  # 번역 기능 제거
                    "--hide-scrollbars",  # 스크롤바 비활성화
                    "--mute-audio",  # 오디오 무음 처리
                    "--headless=new",
                ],
            )

            self._context = await self._browser.new_context(
                locale="en-US",
                extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
                # storage_state=self.storage_state,
                # viewport={"width": 800, "height": 2500},
                # device_scale_factor=2,
            )

    async def close_playwright(self):
        if self._context:
            await self._context.close()

        if self._browser:
            await self._browser.close()

        if self._p:
            await self._p.stop()

    async def get_reels_comment_share_count(self, owner_name):
        print("####### get_reels_comment_share_count")
        view_count = None
        share_count = None
        comment_count = 0

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--disable-gpu",  # GPU 미사용
                    "--no-sandbox",  # 도커 등에서 필수
                    "--disable-dev-shm-usage",  # 메모리 공유 대신 디스크 사용
                    "--disable-setuid-sandbox",  # setuid 샌드박스 비활성화
                    "--disable-extensions",  # 확장 프로그램 제거
                    "--disable-sync",  # 계정 동기화 차단
                    "--disable-default-apps",  # 불필요한 앱 제거
                    "--disable-translate",  # 번역 기능 제거
                    "--hide-scrollbars",  # 스크롤바 비활성화
                    "--mute-audio",  # 오디오 무음 처리
                    "--headless=new",
                ],
            )
            try:
                context = await browser.new_context(
                    locale="en-US",
                    extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
                    # storage_state=self.storage_state,
                    # viewport={"width": 800, "height": 2500},
                    # device_scale_factor=2,
                )

                page = await context.new_page()
                # await stealth_async(page)
                await page.goto(self.url)

                timeout = random.uniform(2, 3)
                await page.wait_for_timeout(timeout * 1000)

                locator = page.locator("text=/\\d+(\\.\\d+)?[A-Z]?\\s*views/i")
                if await locator.count() > 0:
                    view_count = await locator.first.text_content()
                    view_count = view_count.replace("views", "").strip()

                locator = page.locator("text=/\\d+(\\.\\d+)?[A-Z]?\\s*comments/i")
                if await locator.count() > 0:
                    comment_count = await locator.first.text_content()
                    comment_count = comment_count.replace("comments", "").strip()
            finally:
                try:
                    await browser.close()
                except:
                    pass

                try:
                    await context.close()
                except:
                    pass

            return (
                self.parse_abbreviated_number(comment_count),
                self.parse_abbreviated_number(share_count),
                self.parse_abbreviated_number(view_count) if view_count is not None else None,
            )

    async def get_video_view_count(self):
        print("####### get_video_view_count")
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--disable-gpu",  # GPU 미사용
                    "--no-sandbox",  # 도커 등에서 필수
                    "--disable-dev-shm-usage",  # 메모리 공유 대신 디스크 사용
                    "--disable-setuid-sandbox",  # setuid 샌드박스 비활성화
                    "--disable-extensions",  # 확장 프로그램 제거
                    "--disable-sync",  # 계정 동기화 차단
                    "--disable-default-apps",  # 불필요한 앱 제거
                    "--disable-translate",  # 번역 기능 제거
                    "--hide-scrollbars",  # 스크롤바 비활성화
                    "--mute-audio",  # 오디오 무음 처리
                    "--headless=new",
                ],
            )

            try:
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
                    viewport={"width": 1920, "height": 1080},
                    device_scale_factor=2.5,
                    is_mobile=True,
                    has_touch=True,
                    locale="en-US",
                    storage_state=self.storage_state,
                    extra_http_headers={
                        "Accept-Language": "en-US,en;q=0.9",
                    },
                )

                page = await context.new_page()
                await stealth_async(page)

                await page.goto(self.url)
                await self.check_dismiss(page)

                html = await page.content()
                view_count = extract_og_view_count(html)
                if view_count is not None:
                    return view_count

                locator = page.locator("text=/\\d+(\\.\\d+)?[KMB]?\\s*views/i")
                if await locator.count() == 0:
                    return None
                return self.parse_abbreviated_number(await locator.first.text_content())
            finally:
                try:
                    await browser.close()
                except:
                    pass

                try:
                    await context.close()
                except:
                    pass

    async def _get_elements(self, page, selector: str, attributes):
        """주어진 CSS 선택자로 요소를 찾고 속성 값을 가져옴"""
        elements = await page.query_selector_all(selector)
        results = []

        for element in elements:
            # result = {}
            for attribute in attributes:
                if attribute == "innerText":
                    val = await element.inner_text()
                else:
                    val = await element.get_attribute(attribute)

                if val and val.strip():
                    results.append(val.strip())
                    # result[attribute] = val.strip()

            # if result:
            # results.append(result)

        return results

    def teams_message(self, message) -> Message:
        return "NONE"
