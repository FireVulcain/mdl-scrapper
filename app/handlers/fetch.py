import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from app import MYDRAMALIST_WEBSITE
from app.lib.http import client as http_client
from app.handlers.parser import BaseFetch


class FetchDrama(BaseFetch):
    def __init__(self, soup: BeautifulSoup, query: str, code: int, ok: bool) -> None:
        super().__init__(soup, query, code, ok)

    # get the main html container for the each search results
    def _get_main_container(self) -> None:
        if self.soup is None:
            return

        container = self.soup.find("div", class_="app-body")
        if container is None:
            return

        # append scraped data
        # these are the most important drama infos / details

        # TITLE
        # Example: Goblin (2016)
        # Title = Goblin
        # Complete Title = Goblin (2016)
        film_title = container.find("h1", class_="film-title")
        self.info["title"] = film_title.get_text().strip()
        self.info["complete_title"] = film_title.get_text().strip()

        film_subtitle = container.find("div", class_="film-subtitle")

        sub_title = film_subtitle.get_text().strip()

        if sub_title:
            self.info["sub_title"] = sub_title

            # Split the string by the separator '‧'
            parts = sub_title.split("‧")

            # The year is the last part, remove any leading/trailing whitespace
            year_str = parts[-1].strip()

            # Year could be a range, so we keep it as a string
            self.info["year"] = year_str.strip()

        # RATING (could be either N/A or with number)
        self.info["rating"] = self._handle_rating(
            container.find("div", class_="col-film-rating").find("div")
        )

        # POSTER
        self.info["poster"] = self._get_poster(container)

        # SYNOPSIS
        synopsis = container.find("div", class_="show-synopsis").find("p")
        self.info["synopsis"] = (
            synopsis.get_text().replace("Edit Translation", "").strip()
            if synopsis
            else ""
        )

        # CASTS
        __casts = container.find_all("li", class_="list-item col-sm-4")
        casts = []
        for i in __casts:
            __temp_cast = i.find("a", class_="text-primary text-ellipsis")
            __temp_cast_slug = __temp_cast["href"].strip()
            casts.append(
                {
                    "name": __temp_cast.find("b").text.strip(),
                    "profile_image": self._get_poster(i),
                    "slug": __temp_cast_slug,
                    "link": urljoin(MYDRAMALIST_WEBSITE, __temp_cast_slug),
                }
            )
        self.info["casts"] = casts

        # Extract nextEpisodeAiring
        scripts = self.soup.find_all("script", type="text/javascript")
        for script in scripts:
            if script.string and "var nextEpisodeAiring =" in script.string:
                match = re.search(r"var nextEpisodeAiring = ({.*});", script.string)
                if match:
                    next_airing = json.loads(match.group(1))

                    # released_at is a unix timestamp; expose it as readable dates
                    try:
                        released_at = int(next_airing.get("released_at", 0))
                        if released_at:
                            utc_dt = datetime.fromtimestamp(released_at, tz=timezone.utc)
                            next_airing["air_date"] = utc_dt.isoformat()

                            tz_name = next_airing.get("timezone")
                            if tz_name:
                                local_dt = utc_dt.astimezone(ZoneInfo(tz_name))
                                next_airing["air_date_local"] = local_dt.isoformat()
                    except Exception:
                        pass

                    self.info["next_episode_airing"] = next_airing
                    current_episode = float(next_airing["episode_number"]) - 1
                    self.info["current_episode"] = (
                        "0"
                        if current_episode < 0
                        else str(float(next_airing["episode_number"]) - 1).replace(
                            ".0", ""
                        )
                    )
                break

    # get other info
    def _get_other_info(self) -> None:
        if self.soup is None:
            return

        others_container = self.soup.find("div", class_="show-detailsxss")
        if others_container is None:
            return
        others = others_container.find("ul", class_="list m-a-0")

        try:
            self.info["others"] = {}
            all_others = others.find_all("li")
            for i in all_others:
                # get each li from <ul>
                _title = i.find("b").text.strip()
                _key = _title.replace(":", "").replace(" ", "_").lower()

                if _key == "tags":
                    tags = []
                    for a in i.find_all("a", class_="text-primary"):
                        href = a.get("href", "")
                        # href is like /search?adv=titles&th=691&so=popular&or=desc
                        tag_id = None
                        m = re.search(r"[?&]th=(\d+)", href)
                        if m:
                            tag_id = int(m.group(1))
                        tags.append({"id": tag_id, "name": a.get_text(strip=True)})
                    self.info["others"][_key] = tags
                else:
                    self.info["others"][_key] = [
                        i.strip()
                        for i in i.text.replace(_title + " ", "").strip().split(", ")
                    ]

        except Exception:
            # there was a problem while trying to parse
            # the :> other info section
            pass

    # drama info details handler
    def _get(self) -> None:
        self._get_main_container()
        self._get_details(classname="list m-a-0 hidden-md-up")
        self._get_other_info()


class FetchPerson(BaseFetch):
    non_actors = ["screenwriter", "director", "screenwriter & director"]

    def __init__(self, soup: BeautifulSoup, query: str, code: int, ok: bool) -> None:
        super().__init__(soup, query, code, ok)

    def _get_main_container(self) -> None:
        if self.soup is None:
            return

        container = self.soup.find("div", class_="app-body")
        if container is None:
            return

        # append scraped data
        # these are the most important drama infos / details

        # NAME
        self.info["name"] = container.find("h1", class_="film-title").get_text().strip()

        # ABOUT?
        __temp_about = container.find("div", class_="col-lg-8 col-md-8").find(
            "div", class_="col-sm-8 col-lg-12 col-md-12"
        )
        self.info["about"] = (
            __temp_about.text.replace(
                __temp_about.find("div", class_="hidden-md-up").text.strip(), ""
            )
            .replace("Remove ads\n\n", "")
            .strip()
        )

        # IMAGE
        self.info["profile"] = self._get_poster(container)

        # WORKS
        self.info["works"] = {}

        # container: the box holding the filmography tables, its position among
        # the sibling boxes varies (a `Photos` box may come first)
        _works_container = None
        for box_body in container.find("div", class_="col-lg-8 col-md-8").find_all(
            "div", class_="box-body"
        ):
            if box_body.find("table", class_="film-list") is not None:
                _works_container = box_body
                break

        if _works_container is None:
            return

        # each table is preceded by the <h5> naming its category
        _work_tables = _works_container.find_all("table", class_="film-list")
        _work_headers = []
        for k in _work_tables:
            header = k.find_previous("h5")
            _work_headers.append(header.text.strip() if header else "")

        for j, k in zip(_work_headers, _work_tables, strict=False):
            # theaders = ['episodes' if i.text.strip() == '#' else i.text.strip() for i in k.find("thead").find_all("th")]
            # a category can be split across several tables (e.g. two `Drama`
            # tables), so accumulate rows instead of overwriting the key
            rows = [
                self._parse_work_row(i, j) for i in k.find("tbody").find_all("tr")
            ]
            self.info["works"].setdefault(j, []).extend(rows)

    def _parse_work_row(self, i: BeautifulSoup, category: str) -> Dict[str, Any]:
        _raw_year = i.find("td", class_="year").text
        _title_cell = i.find("td", class_="title")

        # the first <a> is the thumbnail (no text); the title sits in <b>
        _title_bold = _title_cell.find("b")
        _raw_title = _title_bold.find("a") if _title_bold else None
        if _raw_title is None:
            _raw_title = _title_cell.find("a")

        # poster url ends with a size code before `.jpg` (`t` is the tiny
        # thumbnail); serve `c` as the default and `f` (full) as a fallback
        _thumb = _title_cell.find("img")
        image = ""
        image_full = ""
        if _thumb:
            _raw_img = _thumb.get("src") or _thumb.get("data-src", "")
            if _raw_img.endswith("t.jpg"):
                image = _raw_img[:-5] + "c.jpg"
                image_full = _raw_img[:-5] + "f.jpg"
            else:
                image = _raw_img
                image_full = _raw_img

        r: Dict[str, Any] = {
            "_slug": i["class"][0],
            "year": _raw_year if _raw_year == "TBA" else int(_raw_year),
            "title": {
                "link": urljoin(MYDRAMALIST_WEBSITE, _raw_title["href"]),
                "name": _raw_title.get_text(strip=True) or _raw_title.get("title", ""),
                "image": image,
                "image_full": image_full,
            },
            "rating": self._handle_rating(
                i.find("td", class_="text-center").find(class_="text-sm")
            ),
        }

        _raw_role = i.find("td", class_="role")

        # applicable only on dramas / tv-shows (this is different for non-actors)
        try:
            _raw_role_name = _raw_role.find("div", class_="name").text.strip()
        except Exception:
            _raw_role_name = None

        # use `type` for non-dramas, etc while `role` otherwise.
        # staff credits (screenwriter, producer, ...) carry no character name at
        # all, so their `roleid` holds the work type instead
        try:
            if category.lower() in FetchPerson.non_actors or _raw_role_name is None:
                r["type"] = _raw_role.find(class_="roleid").text.strip()
            else:
                r["role"] = {
                    "name": _raw_role_name,
                    "type": _raw_role.find("div", class_="roleid").text.strip(),
                }
        except Exception:
            pass

        # not applicable for movies
        try:
            r["episodes"] = int(i.find("td", class_="episodes").text)
        except Exception:
            pass

        return r

    def _get(self) -> None:
        self._get_main_container()
        self._get_details(classname="list m-b-0")


class FetchCast(BaseFetch):
    def __init__(self, soup: BeautifulSoup, query: str, code: int, ok: bool) -> None:
        super().__init__(soup, query, code, ok)

    def _get_main_container(self) -> None:
        if self.soup is None:
            return

        container = self.soup.find("div", class_="app-body")
        if container is None:
            return

        # append scraped data
        # these are the most important drama infos / details

        # TITLE
        self.info["title"] = (
            container.find("h1", class_="film-title").get_text().strip()
        )

        # POSTER
        self.info["poster"] = self._get_poster(container)

        # CASTS?
        self.info["casts"] = {}
        __casts_container = container.find("div", class_="box cast-credits").find(
            "div", class_="box-body"
        )

        __temp_cast_headers = __casts_container.find_all("h3")
        __temp_cast_lists = __casts_container.find_all("ul")

        for j, k in zip(__temp_cast_headers, __temp_cast_lists, strict=False):
            casts = []
            for i in k.find_all("li"):
                __temp_cast = i.find("a", class_="text-primary")
                __temp_cast_slug = __temp_cast["href"].strip()
                __temp_cast_data = {
                    "name": __temp_cast.find("b").text.strip(),
                    "profile_image": self._get_poster(i).replace(
                        "s.jpg", "m.jpg"
                    ),  # replaces the small images to a link with a bigger one
                    "slug": __temp_cast_slug,
                    "link": urljoin(MYDRAMALIST_WEBSITE, __temp_cast_slug),
                }

                try:
                    __temp_cast_data["role"] = {
                        "name": i.find("small").text.strip(),
                        "type": i.find("small", class_="text-muted").text.strip(),
                    }
                except Exception:
                    pass

                casts.append(__temp_cast_data)

            self.info["casts"][j.text.strip()] = casts

    def _get(self) -> None:
        self._get_main_container()


class FetchReviews(BaseFetch):
    def __init__(self, soup: BeautifulSoup, query: str, code: int, ok: bool) -> None:
        super().__init__(soup, query, code, ok)

    def _get_main_container(self) -> None:  # noqa: C901
        if self.soup is None:
            return

        container = self.soup.find("div", class_="app-body")
        if container is None:
            return

        # append scraped data
        # these are the most important drama infos / details

        # TITLE
        self.info["title"] = (
            container.find("h1", class_="film-title").get_text().strip()
        )

        # POSTER
        self.info["poster"] = self._get_poster(container)

        # REVIEWS?
        self.info["reviews"] = []
        __temp_reviews = container.find_all("div", class_="review")

        for i in __temp_reviews:
            __temp_review: Dict[str, Any] = {}

            try:
                # reviewer / person
                __temp_review["reviewer"] = {
                    "name": i.find("a").text.strip(),
                    "user_link": urljoin(MYDRAMALIST_WEBSITE, i.find("a")["href"]),
                    "user_image": self._get_poster(i).replace(
                        "1t", "1c"
                    ),  # replace 1t to 1c so that it will return a bigger image than the smaller one
                    "info": i.find("div", class_="user-stats").text.strip(),
                }

                __temp_review_ratings = i.find(
                    "div", class_="box pull-right text-sm m-a-sm"
                )
                __temp_review_ratings_overall = __temp_review_ratings.find(
                    "div", class_="rating-overall"
                )

                # start parsing the review section
                __temp_review_contents = []

                __temp_review_container = i.find(
                    "div", class_=re.compile("review-body")
                )

                __temp_review_spoiler = __temp_review_container.find(
                    "div", "review-spoiler"
                )
                if __temp_review_spoiler is not None:
                    __temp_review_contents.append(__temp_review_spoiler.text.strip())

                __temp_review_strong = __temp_review_container.find("strong")
                if __temp_review_strong is not None:
                    __temp_review_contents.append(__temp_review_strong.text.strip())

                __temp_review_read_more = __temp_review_container.find(
                    "p", class_="read-more"
                ).text.strip()
                __temp_review_vote = __temp_review_container.find(
                    "div", class_="review-helpful"
                ).text.strip()

                for i in __temp_review_container.find_all("br"):
                    i.replace_with("\n")

                __temp_review_content = (
                    __temp_review_container.text.replace(
                        __temp_review_ratings.text.strip(), ""
                    )
                    .replace(__temp_review_read_more, "")
                    .replace(__temp_review_vote, "")
                )

                if __temp_review_spoiler is not None:
                    __temp_review_content = __temp_review_content.replace(
                        __temp_review_spoiler.text.strip(), ""
                    )
                if __temp_review_strong is not None:
                    __temp_review_content = __temp_review_content.replace(
                        __temp_review_strong.text.strip(), ""
                    )

                __temp_review_contents.append(__temp_review_content.strip())
                __temp_review["review"] = __temp_review_contents
                # end parsing the review section

                __temp_review["ratings"] = {
                    "overall": float(
                        __temp_review_ratings_overall.find("span").text.strip()
                    )
                }
                __temp_review_ratings_others = __temp_review_ratings.find(
                    "div", class_="review-rating"
                ).find_all("div")

                # other review ratings, it might be different in each box?
                for k in __temp_review_ratings_others:
                    __temp_review["ratings"][
                        k.text.replace(k.find("span").text.strip(), "").strip()
                    ] = float(k.find("span").text.strip())

            except Exception as e:
                print(e)
                # if failed to parse, do nothing
                pass

            # append to list
            self.info["reviews"].append(__temp_review)

    def _get(self) -> None:
        self._get_main_container()


class FetchDramaList(BaseFetch):
    # msv2 status column -> label used by the classic layout, kept for consistency
    _MSV2_STATUS_LABELS = {
        "watching": "Currently Watching",
        "completed": "Completed",
        "on hold": "On Hold",
        "plan to watch": "Plan to Watch",
        "dropped": "Dropped",
    }

    # msv2 lazy-loads 100 rows per page, cap the loop as a safety net
    _MSV2_MAX_PAGES = 100

    def __init__(self, soup: BeautifulSoup, query: str, code: int, ok: bool) -> None:
        super().__init__(soup, query, code, ok)

    @classmethod
    async def scrape(cls, query: str, t: str) -> "FetchDramaList":
        obj: "FetchDramaList" = await super().scrape(query=query, t=t)

        if obj.ok and obj.soup is not None:
            if obj.soup.find("table", class_="msv2-table") is not None:
                await obj._fetch_msv2_pages()

        return obj

    async def _fetch_msv2_pages(self) -> None:
        if self.soup is None:
            return

        table = self.soup.find("table", class_="msv2-table")
        if table is None:
            return

        tbody = table.find("tbody") or table
        url = urljoin(MYDRAMALIST_WEBSITE, self.query)
        client = http_client()

        page = 2
        while page <= self._MSV2_MAX_PAGES:
            try:
                resp = client.post(
                    url,
                    headers={
                        **self.headers,
                        "x-requested-with": "XMLHttpRequest",
                        "content-type": "application/json",
                    },
                    json={
                        "page": page,
                        "sort_by": "title",
                        "sort_order": "asc",
                        "filters": {
                            "search": "",
                            "list": "0",
                            "country": "",
                            "type": "",
                            "category": "",
                            "tags": [],
                            "genres": [],
                        },
                        "settings": {},
                        "layout": {},
                        "roll_dice": None,
                    },
                )
            except Exception:
                break

            if resp.status_code != 200 or not resp.text.strip():
                break

            fragment = BeautifulSoup(resp.text, "html.parser")
            rows = fragment.find_all("tr")
            if not rows:
                break

            for row in rows:
                tbody.append(row)

            limit = int(resp.headers.get("x-pagination-limit", len(rows) or 100))
            if len(rows) < limit:
                break

            page += 1

    def _get_main_container(self) -> None:
        if self.soup is None:
            return

        container = self.soup.find_all("div", class_="mdl-style-list")
        if container:
            titles = [self._parse_title(item) for item in container]
            dramas = [self._parse_drama(item) for item in container]
            stats = [self._parse_total_stats(item) for item in container]

            items = {}
            for title, drama, stat in zip(titles, dramas, stats, strict=False):
                items[title] = {"items": drama, "stats": stat}

            self.info["list"] = items
            return

        msv2_table = self.soup.find("table", class_="msv2-table")
        if msv2_table is not None:
            self.info["list"] = self._parse_msv2_table(msv2_table)

    def _parse_msv2_table(self, table: BeautifulSoup) -> Dict[str, Any]:
        grouped: Dict[str, List[Dict[str, str]]] = {}
        seen_ids: set = set()

        for row in table.find_all("tr"):
            title_el = row.find("td", class_="msv2-i-title")
            status_el = row.find("td", class_="msv2-i-status")
            if title_el is None or status_el is None:
                continue

            link = title_el.find("a")
            if link is None:
                continue

            # MDL's paginated fragments can overlap between pages (unstable
            # sort on ties), so dedupe on the drama id.
            drama_id = link.get("href", "").split("/")[-1]
            if not drama_id or drama_id in seen_ids:
                continue
            seen_ids.add(drama_id)

            score_el = row.find("td", class_="msv2-i-score")
            eps_el = row.find("td", class_="msv2-i-eps")
            progress_el = row.find("td", class_="msv2-i-progress")

            episode_seen = ""
            episode_total = ""
            if progress_el is not None:
                seen_span = progress_el.find("span", class_="num-seen")
                total_span = progress_el.find("span", class_="num-total")
                if seen_span is not None:
                    episode_seen = seen_span.get_text(strip=True)
                if total_span is not None:
                    episode_total = total_span.get_text(strip=True)

                if not episode_seen or not episode_total:
                    match = re.search(r"(\d+)\s*/\s*(\d+)", progress_el.get_text())
                    if match:
                        episode_seen = episode_seen or match.group(1)
                        episode_total = episode_total or match.group(2)

            if not episode_total and eps_el is not None:
                episode_total = eps_el.get_text(strip=True)

            score = ""
            if score_el is not None:
                score_span = score_el.find("span", class_="score")
                score = (
                    score_span.get_text(strip=True)
                    if score_span is not None
                    else score_el.get_text(strip=True)
                )

            status_raw = status_el.get_text(strip=True)
            status_label = self._MSV2_STATUS_LABELS.get(
                status_raw.lower(), status_raw
            )

            # This layout renders the artwork the classic one has no column for,
            # already at the thumbnail size MDL uses on its own hover card. It is
            # lazy-loaded, so the real address may sit in data-src.
            poster = ""
            img = title_el.find("img")
            if img is not None:
                poster = img.get("data-src") or img.get("src") or ""

            # And it carries MDL's own rating beside the member's, which the
            # classic layout never shows at all.
            mdl_score = ""
            mdl_el = row.find("td", class_="msv2-i-mdlscore")
            if mdl_el is not None:
                mdl_span = mdl_el.find("span", class_="score")
                mdl_score = (
                    mdl_span.get_text(strip=True)
                    if mdl_span is not None
                    else mdl_el.get_text(strip=True)
                )

            parsed_item = {
                "name": link.get_text(strip=True),
                "id": drama_id,
                "score": score,
                "episode_seen": episode_seen,
                "episode_total": episode_total,
                "country": self._cell_text(row, "msv2-i-country"),
                "year": self._cell_text(row, "msv2-i-year"),
                "type": "",
                "kind": "",
                "poster": poster,
                "mdl_score": mdl_score,
            }

            grouped.setdefault(status_label, []).append(parsed_item)

        return {
            status: {
                "items": drama_items,
                "stats": {"Dramas": str(len(drama_items))},
            }
            for status, drama_items in grouped.items()
        }

    def _parse_title(self, item: BeautifulSoup) -> str:
        label = item.find("h3", class_="mdl-style-list-label")
        if label is None:
            return ""

        return label.get_text(strip=True)

    def _parse_total_stats(self, item: BeautifulSoup) -> Dict[str, str]:
        drama_stats = item.find("label", class_="mdl-style-dramas")
        tvshows_stats = item.find("label", class_="mdl-style-tvshows")
        episodes_stats = item.find("label", class_="mdl-style-episodes")
        movies_stats = item.find("label", class_="mdl-style-movies")
        days_stats = item.find("label", class_="mdl-style-days")

        return {
            label.find("span", class_="name").get_text(strip=True): label.find(
                "span", class_="cnt"
            ).get_text(strip=True)
            for label in [
                drama_stats,
                tvshows_stats,
                episodes_stats,
                movies_stats,
                days_stats,
            ]
            if label is not None
        }

    @staticmethod
    def _cell_text(row: BeautifulSoup, css_class: str) -> str:
        cell = row.find("td", class_=css_class)
        return cell.get_text(strip=True) if cell is not None else ""

    @classmethod
    def _cell(cls, row: BeautifulSoup, name: str) -> str:
        return cls._cell_text(row, f"mdl-style-col-{name}")

    def _parse_drama(self, item: BeautifulSoup) -> List[Dict[str, str]]:
        """One row at a time, which is both more complete and less fragile.

        This used to collect four lists by CSS class — every a.title, every
        span.score, every span.episode-seen — and zip them together. That holds
        only while every row carries all four. A single unrated title has no
        span.score, and from that row on every score belongs to the wrong
        drama; `strict=False` hides it by truncating instead of raising.

        Walking the rows also reaches the three columns the classic layout has
        always rendered and this never looked at: country, year and type. They
        cost nothing extra, the markup is already downloaded, and they are the
        difference between a list of names and a list one can actually read.
        """
        parsed_data: List[Dict[str, str]] = []

        for row in item.find_all("tr"):
            title_cell = row.find("td", class_="mdl-style-col-title")
            if title_cell is None:
                continue

            link = title_cell.find("a", class_="title")
            if link is None:
                continue

            progress = row.find("td", class_="mdl-style-col-progress")
            seen = progress.find("span", class_="episode-seen") if progress else None
            total = progress.find("span", class_="episode-total") if progress else None

            # MDL repeats country and format together here for narrow screens —
            # "Chinese Drama" — which is the phrasing it uses on its own hover
            # card, so it is worth carrying as it stands rather than rebuilt.
            kind = title_cell.find("div", class_="text-muted")

            parsed_data.append(
                {
                    "name": link.get_text(strip=True),
                    "id": link.get("href", "").split("/")[-1],
                    "score": self._cell(row, "score"),
                    "episode_seen": seen.get_text(strip=True) if seen is not None else "",
                    "episode_total": total.get_text(strip=True) if total is not None else "",
                    "country": self._cell(row, "country"),
                    "year": self._cell(row, "year"),
                    "type": self._cell(row, "type"),
                    "kind": kind.get_text(strip=True) if kind is not None else "",
                    # Both layouts answer with the same keys so a caller never has
                    # to know which one it got. The classic one renders no artwork
                    # and no MDL rating, so these stay empty rather than absent.
                    "poster": "",
                    "mdl_score": "",
                }
            )

        return parsed_data

    def _get(self) -> None:
        self._get_main_container()


class FetchList(BaseFetch):
    def __init__(self, soup: BeautifulSoup, query: str, code: int, ok: bool) -> None:
        super().__init__(soup, query, code, ok)

    def _get_main_container(self) -> None:
        if self.soup is None:
            return

        container = self.soup.find("div", class_="app-body")
        if container is None:
            return

        # get list title
        header = container.find("div", class_="box-header")
        self.info["title"] = header.find("h1").get_text().strip()

        description = header.find("div", class_="description")
        self.info["description"] = (
            description.get_text().strip() if description is not None else ""
        )

        # get list
        container_list = container.find("div", class_="collection-list")
        all_items = container_list.find_all("li")
        list_items = []
        for i in all_items:
            i_url = i.find("a").get("href")
            if "/people/" in i_url:
                list_items.append(self._parse_person(i))
                continue

            list_items.append(self._parse_show(i))

        self.info["list"] = list_items

    def _parse_person(self, item: BeautifulSoup) -> Dict[str, Any]:
        # parse person image
        person_img_container = item.find("img", class_="img-responsive")
        if person_img_container is None:
            person_img_container = {}
        person_img_src = str(person_img_container.get("data-src", "")).split("/1280/")
        person_img = ""
        if len(person_img_src) > 1:
            person_img = person_img_src[1]
        else:
            person_img = person_img_src[0]

        person_img = person_img.replace(
            "s.jpg", "m.jpg"
        )  # replace image url to give the bigger size

        item_header = item.find("div", class_="content")
        if item_header is None:
            return {
                "name": "",
                "type": "person",
                "image": person_img,
                "slug": "",
                "url": "",
            }
        person_name = item_header.find("a").get_text().strip()
        person_slug = item_header.find("a").get("href")
        person_url = urljoin(MYDRAMALIST_WEBSITE, person_slug)

        person_nationality_container = item.find(class_="text-muted")
        person_nationality = (
            person_nationality_container.get_text().strip()
            if person_nationality_container
            else ""
        )
        person_details_xx = item.find_all("p")
        person_details = ""
        if len(person_details_xx) > 1:
            person_details = person_details_xx[-1].get_text().strip()

        return {
            "name": person_name,
            "type": "person",  # todo: change this
            "image": person_img,
            "slug": person_slug,
            "url": person_url,
            "nationality": person_nationality,
            "details": person_details,
        }

    def _parse_show(self, item: BeautifulSoup) -> Dict[str, Any]:
        # parse list image
        list_img_container = item.find("img", class_="img-responsive")
        if list_img_container is None:
            list_img_container = {}
        list_img_src = str(list_img_container.get("data-src", "")).split("/1280/")
        list_img = ""
        if len(list_img_src) > 1:
            list_img = list_img_src[1]
        else:
            list_img = list_img_src[0]

        list_img = list_img.replace(
            "t.jpg", "c.jpg"
        )  # replace image url to give the bigger size

        list_header = item.find("h2")
        if list_header is None:
            return {
                "title": "",
                "image": list_img,
                "rank": "",
                "url": "",
                "slug": "",
                "type": "",
                "year": "",
                "episodes": None,
                "short_summary": "",
            }
        list_title = list_header.find("a").get_text().strip()
        list_title_rank = (
            list_header.get_text().replace(list_title, "").strip().strip(".")
        )
        list_url = urljoin(MYDRAMALIST_WEBSITE, list_header.find("a").get("href"))
        list_slug = list_header.find("a").get("href")

        # parse example: `Korean Drama - 2020, 16 episodes`
        list_details_container = item.find(class_="text-muted")  # could be `p` or `div`
        list_details_xx = (
            list_details_container.get_text().split(",")
            if list_details_container
            else ""
        )
        list_details_type = list_details_xx[0].split("-")[0].strip()
        list_details_year = list_details_xx[0].split("-")[1].strip()

        list_details_episodes = None
        if len(list_details_xx) > 1:
            list_details_episodes = int(
                list_details_xx[1].replace("episodes", "").strip()
            )

        # try to get description, it is missing on some lists
        list_short_summary = ""
        list_short_summary_container = item.find("div", class_="col-xs-12 m-t-sm")
        if list_short_summary_container is not None:
            list_short_summary = (
                list_short_summary_container.get_text()
                .replace("...more", "...")
                .strip()
            )

        return {
            "title": list_title,
            "image": list_img,
            "rank": list_title_rank,
            "url": list_url,
            "slug": list_slug,
            "type": list_details_type,
            "year": list_details_year,
            "episodes": list_details_episodes,
            "short_summary": list_short_summary,
        }

    def _get(self) -> None:
        self._get_main_container()


class FetchEpisode(BaseFetch):
    """Scrapes a single episode detail page, including synopsis."""

    def __init__(self, soup: BeautifulSoup, query: str, code: int, ok: bool) -> None:
        super().__init__(soup, query, code, ok)

    def _get_main_container(self) -> None:
        if self.soup is None:
            return

        container = self.soup.find("div", class_="app-body")
        if container is None:
            return

        # Drama + episode title (e.g. "The Prisoner of Beauty Episode 1")
        film_title = container.find("h1", class_="film-title")
        self.info["title"] = film_title.get_text(strip=True) if film_title else ""

        # Individual episode title (e.g. "Episode Title: Feud")
        episode_title_tag = container.find("h2", class_="text-md")
        if episode_title_tag:
            raw = episode_title_tag.get_text(strip=True)
            self.info["episode_title"] = raw.replace("Episode Title:", "").strip()

        # Cover image
        cover_img = container.find("img", class_="img-responsive")
        self.info["image"] = cover_img["src"] if cover_img and cover_img.get("src") else ""

        # Rating
        rating_box = container.find("div", class_="col-film-rating")
        if rating_box:
            self.info["rating"] = self._handle_rating(rating_box.find("div"))

        # Synopsis
        synopsis = container.find("div", class_="show-synopsis")
        self.info["synopsis"] = synopsis.get_text(strip=True) if synopsis else ""

        # Air date
        show_details = container.find("div", class_="show-details")
        if show_details:
            for li in show_details.find_all("li"):
                b = li.find("b")
                if b and "Aired" in b.get_text():
                    self.info["air_date"] = li.get_text(strip=True).replace("Aired:", "").strip()
                    break

    def _get_reviews(self) -> None:
        if self.soup is None:
            return

        reviews_container = self.soup.find("div", class_="reviews")
        if reviews_container is None:
            self.info["reviews"] = []
            return

        reviews = []
        for review in reviews_container.find_all("div", class_="review"):
            r: Dict[str, Any] = {}

            r["id"] = review.get("id", "").replace("review-", "")

            header_info = review.find("div", class_="header-info")
            if header_info:
                author_tag = header_info.find("a", class_="text-primary")
                if author_tag:
                    r["author"] = author_tag.get_text(strip=True)
                    r["author_url"] = urljoin(MYDRAMALIST_WEBSITE, author_tag.get("href", ""))

            avatar = review.find("span", class_="avatar")
            if avatar:
                img = avatar.find("img")
                r["author_avatar"] = img.get("src", "") if img else ""

            user_stats = review.find("div", class_=re.compile(r"user-stats"))
            if user_stats:
                b = user_stats.find("b")
                try:
                    r["helpful_count"] = int(b.get_text(strip=True)) if b else 0
                except ValueError:
                    r["helpful_count"] = 0

            date_tag = review.find("small", class_="datetime")
            r["date"] = date_tag.get_text(strip=True) if date_tag else ""

            rating_fill = review.find("span", class_="fill")
            if rating_fill:
                m = re.search(r"width:(\d+)%", rating_fill.get("style", ""))
                if m:
                    r["rating"] = int(m.group(1)) / 10

            rating_panel = review.find("p", class_="rating-panel")
            if rating_panel:
                b = rating_panel.find("b")
                r["headline"] = b.get_text(strip=True) if b else ""

            body_container = review.find("div", class_=re.compile(r"review-body"))
            if body_container:
                for tag in body_container.find_all(["p", "div"], class_=["rating-panel", "review-helpful", "read-more"]):
                    tag.decompose()
                for br in body_container.find_all("br"):
                    br.replace_with("\n")
                r["body"] = body_container.get_text(strip=True)

            reviews.append(r)

        self.info["reviews"] = reviews

    def _get(self) -> None:
        self._get_main_container()
        self._get_reviews()


class FetchRecommendations(BaseFetch):
    def __init__(self, soup: BeautifulSoup, query: str, code: int, ok: bool) -> None:
        super().__init__(soup, query, code, ok)

    def _get_main_container(self) -> None:
        if self.soup is None:
            return

        container = self.soup.find("div", class_="app-body")
        if container is None:
            return

        recs: List[Dict[str, Any]] = []
        for item in container.find_all("div", class_="box-body"):
            img_tag = item.find("img", class_="img-responsive")
            link_tag = item.find("a", class_="text-primary")
            if img_tag is None or link_tag is None:
                continue

            href = link_tag.get("href", "").strip()
            img_url = img_tag.get("src", "")

            # --- transform thumbnail URL to full-size ---
            if img_url.endswith("t.jpg"):
                img_url = img_url[:-5] + "f.jpg"  # replace last "t.jpg" with "f.jpg"
            elif "_4t." in img_url:
                img_url = img_url.replace("_4t.", "_4f.")

            recs.append({
                "img": img_url,
                "title": link_tag.get_text(strip=True),
                "url": href,
            })

        self.info["recommendations"] = recs

    def _get(self) -> None:
        self._get_main_container()


class FetchTopShows(BaseFetch):
    def __init__(self, soup: BeautifulSoup, query: str, code: int, ok: bool) -> None:
        super().__init__(soup, query, code, ok)

    def _get_main_container(self) -> None:
        if self.soup is None:
            return

        container = self.soup.find("div", class_="app-body")
        if container is None:
            return

        shows: List[Dict[str, Any]] = []

        for box in container.find_all("div", class_="box"):
            box_id = box.get("id", "").replace("mdl-", "")
            if not box_id.isdigit():
                continue

            box_body = box.find("div", class_="box-body")
            if box_body is None:
                continue

            # Image (prefer data-src, fall back to src)
            img_tag = box_body.find("img", class_="img-responsive")
            img_url = ""
            img_alt = ""
            if img_tag:
                img_url = img_tag.get("data-src") or img_tag.get("src", "")
                base, _, qs = img_url.partition("?")
                if "_4s." in base:
                    img_url = base.replace("_4s.", "_4f.") + ("?" + qs if qs else "")
                elif base.endswith("s.jpg"):
                    img_url = base[:-5] + "c.jpg" + ("?" + qs if qs else "")
                img_alt = img_tag.get("alt", "")

            # Slug / URL
            cover_link = box_body.find("a", class_="block")
            slug = cover_link.get("href", "").strip() if cover_link else ""

            # Rank
            rank_tag = box_body.find("div", class_="ranking")
            rank_raw = rank_tag.find("span").get_text(strip=True) if rank_tag else ""
            try:
                rank = int(rank_raw.lstrip("#"))
            except ValueError:
                rank = None

            # Title
            title_tag = box_body.find("h6", class_="title")
            title = title_tag.find("a").get_text(strip=True) if title_tag else img_alt

            # Details: "Korean Drama - 2025, 16 episodes"
            details_tag = box_body.find("span", class_="text-muted")
            details_text = details_tag.get_text(strip=True) if details_tag else ""
            drama_type = year = ""
            episodes: Any = None
            if details_text:
                parts = details_text.split(",")
                type_year = parts[0].split("-")
                drama_type = type_year[0].strip()
                year = type_year[1].strip() if len(type_year) > 1 else ""
                if len(parts) > 1:
                    try:
                        episodes = int(parts[1].replace("episodes", "").strip())
                    except ValueError:
                        pass

            # Rating
            rating_tag = box_body.find("span", class_="score")
            rating: Any = None
            if rating_tag:
                rating = self._handle_rating(rating_tag)

            # Synopsis (p that does NOT contain the rating span)
            synopsis = ""
            for p in box_body.find_all("p"):
                if p.find("span", class_="score"):
                    continue
                synopsis = p.get_text(strip=True)
                break

            shows.append({
                "id": box_id,
                "title": title,
                "original_title": img_alt if img_alt != title else "",
                "url": slug,
                "img": img_url,
                "rank": rank,
                "type": drama_type,
                "year": year,
                "episodes": episodes,
                "rating": rating,
                "synopsis": synopsis,
            })

        # Pagination — MDL only renders a `last` link on large result sets; on
        # short ones it shows just the numbered pages and a `next`, so take the
        # total from the highest page number appearing anywhere in the widget.
        pagination: Dict[str, Any] = {}
        pag_ul = container.find("ul", class_="pagination")
        if pag_ul:
            active = pag_ul.find("li", class_="active")
            current_page = 1
            if active:
                try:
                    current_page = int(active.get_text(strip=True))
                except ValueError:
                    pass
            pagination["current_page"] = current_page

            page_numbers = [current_page]
            for a in pag_ul.find_all("a", class_="page-link"):
                m = re.search(r"page=(\d+)", a.get("href", ""))
                if m:
                    page_numbers.append(int(m.group(1)))
            pagination["total_pages"] = max(page_numbers)

            next_link = pag_ul.find("li", class_="next")
            next_a = next_link.find("a", href=True) if next_link else None
            pagination["has_next"] = bool(next_a and next_a["href"].strip())

        self.info["shows"] = shows
        self.info["pagination"] = pagination

    def _get(self) -> None:
        self._get_main_container()


class FetchEpisodes(BaseFetch):
    def __init__(self, soup, query, code, ok):
        super().__init__(soup, query, code, ok)

    def _get_main_container(self) -> None:
        if self.soup is None:
            return

        container = self.soup.find("div", class_="app-body")
        if container is None:
            return

        title = self._parse_title(container)
        episodes = self._parse_episodes(container)

        self.info = {
            "title": title,
            "episodes": episodes,
        }

    def _parse_episodes(self, item: BeautifulSoup) -> List[Dict[str, Any]]:
        episodes_container = item.find("div", class_="episodes")
        if episodes_container is None:
            return []

        epi_list = episodes_container.find_all(
            "div", class_="col-xs-12 col-sm-6 col-md-4 p-a episode"
        )

        episodes = []
        for epi in epi_list:
            title = epi.find("h2", class_="title").get_text(strip=True)

            cover = epi.find("div", class_="cover")
            img = cover.find("img")["data-src"]
            link = urljoin(MYDRAMALIST_WEBSITE, cover.find("a")["href"])

            rating = (
                epi.find("div", class_="rating-panel m-b-0")
                .find("div")
                .get_text(strip=True)
            )

            air_date: str | None = None
            try:
                air_date = epi.find("div", class_="air-date").get_text(strip=True)
            except Exception:
                pass

            episodes.append(
                {
                    "title": title,
                    "image": img,
                    "link": link,
                    "rating": rating,
                    "air_date": air_date,
                }
            )

        return episodes

    def _parse_title(self, item: BeautifulSoup) -> str:
        title_container = item.find("h1", class_="film-title")

        return title_container.get_text(strip=True) if title_container else ""

    def _get(self):
        self._get_main_container()


class FetchPhotos(BaseFetch):
    """Scrapes a photo gallery (drama or person)."""

    def __init__(self, soup: BeautifulSoup, query: str, code: int, ok: bool) -> None:
        super().__init__(soup, query, code, ok)

    def _get_main_container(self) -> None:
        if self.soup is None:
            return

        container = self.soup.find("div", class_="app-body")
        if container is None:
            return

        photos: List[Dict[str, Any]] = []
        # the person photos page has no film-title heading, so fall back to the
        # name carried by each image's `alt`
        alt_name = ""
        for a in container.find_all("a", class_="block", href=True):
            href = a["href"].strip()
            if not href.startswith("/photos/"):
                continue

            img = a.find("img")
            image = img.get("src", "") if img else ""
            if not alt_name and img:
                alt_name = img.get("alt", "").strip()

            # thumbnails end with `m.jpg`; the full-size variant uses `f.jpg`
            image_full = image
            if image.endswith("m.jpg"):
                image_full = image[:-5] + "f.jpg"

            photos.append(
                {
                    "id": href.split("/")[-1],
                    "link": urljoin(MYDRAMALIST_WEBSITE, href),
                    "image": image,
                    "image_full": image_full,
                }
            )

        title_tag = container.find("h1", class_="film-title")
        self.info["title"] = (
            title_tag.get_text(strip=True) if title_tag else alt_name
        )
        self.info["photos"] = photos
        self.info["pagination"] = self._parse_pagination(container)

    def _parse_pagination(self, container: BeautifulSoup) -> Dict[str, Any]:
        pagination: Dict[str, Any] = {}

        pag_ul = container.find("ul", class_="pagination")
        if pag_ul is None:
            return pagination

        active = pag_ul.find("li", class_="active")
        if active:
            try:
                pagination["current_page"] = int(active.get_text(strip=True))
            except ValueError:
                pass

        # only the `last` link reliably carries the total page count
        last_link = pag_ul.find("li", class_="last")
        if last_link:
            a = last_link.find("a")
            href = a.get("href", "") if a else ""
            m = re.search(r"page=(\d+)", href)
            if m:
                pagination["total_pages"] = int(m.group(1))

        # single-page galleries expose no pagination controls
        pagination.setdefault("current_page", 1)
        pagination.setdefault("total_pages", pagination["current_page"])

        return pagination

    def _get(self) -> None:
        self._get_main_container()


class FetchRatings(BaseFetch):
    """Scrapes the rating trend from a title's statistics page.

    The `overall_ratings` chart is drawn client-side by Highcharts, so its SVG
    never exists in the raw HTML. The data behind it, however, is embedded
    server-side in an inline <script> as the Highcharts config, so we parse that
    config rather than the (JS-generated) chart.
    """

    def __init__(self, soup: BeautifulSoup, query: str, code: int, ok: bool) -> None:
        super().__init__(soup, query, code, ok)

    def _get_main_container(self) -> None:
        if self.soup is None:
            return

        container = self.soup.find("div", class_="app-body")
        if container is None:
            return

        title_tag = container.find("h1", class_="film-title")
        self.info["title"] = title_tag.get_text(strip=True) if title_tag else ""

        self.info["overall_ratings"] = self._parse_overall_ratings()

    def _parse_overall_ratings(self) -> List[Dict[str, Any]]:
        # find the inline script that configures the charts
        script = None
        for s in self.soup.find_all("script"):
            if s.string and "#overall_ratings" in s.string:
                script = s.string
                break
        if script is None:
            return []

        # isolate the overall_ratings chart config from the neighbouring ones
        start = script.find("#overall_ratings")
        nxt = script.find("$('#", start + 1)
        block = script[start:nxt] if nxt != -1 else script[start:]

        # within the block the first `categories:` is the x-axis (dates) and the
        # first `data:` is the Ratings series (plotLines use `value:`, not data)
        cats_m = re.search(r"categories:\s*(\[.*?\])", block, re.DOTALL)
        data_m = re.search(r"data:\s*(\[.*?\])", block, re.DOTALL)
        if cats_m is None or data_m is None:
            return []

        try:
            categories = json.loads(cats_m.group(1))
            data = json.loads(data_m.group(1))
        except Exception:
            return []

        return [
            {"date": date, "rating": rating}
            for date, rating in zip(categories, data, strict=False)
        ]

    def _get(self) -> None:
        self._get_main_container()
