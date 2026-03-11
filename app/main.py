from typing import Any, Dict

import cloudscraper
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from app.lib.msgspec_json import MsgSpecJSONResponse
from app.utils import fetch_func, search_func

app = FastAPI(
    title="Kuryana",
    default_response_class=MsgSpecJSONResponse,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def index() -> Dict[str, Any]:
    return {"message": "A Simple and Basic MDL Scraper API"}


@app.get("/search/q/{query}")
async def search(query: str, response: Response) -> Dict[str, Any]:
    code, r = await search_func(query=query)

    response.status_code = code
    return r


@app.get("/id/{drama_id}")
async def fetch(drama_id: str, response: Response) -> Dict[str, Any]:
    code, r = await fetch_func(query=drama_id, t="drama")

    response.status_code = code
    return r


@app.get("/id/{drama_id}/cast")
async def fetch_cast(drama_id: str, response: Response) -> Dict[str, Any]:
    code, r = await fetch_func(query=f"{drama_id}/cast", t="cast")

    response.status_code = code
    return r


@app.get("/id/{drama_id}/episodes")
async def fetch_episodes(drama_id: str, response: Response) -> Dict[str, Any]:
    code, r = await fetch_func(query=f"{drama_id}/episodes", t="episodes")

    response.status_code = code
    return r


@app.get("/id/{drama_id}/episode/{episode_number}")
async def fetch_episode(drama_id: str, episode_number: int, response: Response) -> Dict[str, Any]:
    code, r = await fetch_func(query=f"{drama_id}/episode/{episode_number}", t="episode")

    response.status_code = code
    return r


@app.get("/id/{drama_id}/recs")
async def fetch_recs(drama_id: str, response: Response) -> Dict[str, Any]:
    code, r = await fetch_func(query=f"{drama_id}/recs", t="recs")

    response.status_code = code
    return r


@app.get("/id/{drama_id}/reviews")
async def fetch_reviews(
    drama_id: str, response: Response, page: int = 1
) -> Dict[str, Any]:
    code, r = await fetch_func(query=f"{drama_id}/reviews?page={page}", t="reviews")

    response.status_code = code
    return r


@app.get("/people/{person_id}")
async def person(person_id: str, response: Response) -> Dict[str, Any]:
    code, r = await fetch_func(query=f"people/{person_id}", t="person")

    response.status_code = code
    return r


@app.get("/dramalist/{user_id}")
async def dramalist(user_id: str, response: Response) -> Dict[str, Any]:
    code, r = await fetch_func(query=f"dramalist/{user_id}", t="dramalist")

    response.status_code = code
    return r


@app.get("/list/{list_id}")
async def lists(list_id: str, response: Response) -> Dict[str, Any]:
    code, r = await fetch_func(query=f"list/{list_id}", t="lists")

    response.status_code = code
    return r


_TOP_COUNTRY_CODES: Dict[str, int] = {
    "korean": 3,
    "japanese": 1,
    "chinese": 2,
    "taiwanese": 5,
    "hongkong": 4,
    "thai": 6,
    "philippine": 140,
    "singaporean": 157,
}

_TOP_STATUS_CODES: Dict[str, int] = {
    "ongoing": 1,
    "upcoming": 2,
    "completed": 3,
}

_TOP_SORT_VALUES = {"top", "popular"}

_TOP_GENRE_CODES: Dict[str, int] = {
    "action": 1,
    "adventure": 5,
    "animals": 9,
    "business": 13,
    "comedy": 17,
    "crime": 21,
    "detective": 38,
    "documentary": 35,
    "drama": 25,
    "family": 29,
    "fantasy": 32,
    "food": 2,
    "friendship": 6,
    "historical": 10,
    "horror": 14,
    "investigation": 42,
    "law": 18,
    "life": 22,
    "manga": 44,
    "martial_arts": 26,
    "mature": 40,
    "medical": 30,
    "melodrama": 33,
    "military": 3,
    "music": 7,
    "mystery": 11,
    "political": 41,
    "psychological": 15,
    "romance": 19,
    "school": 23,
    "sci_fi": 27,
    "sitcom": 36,
    "sports": 31,
    "supernatural": 34,
    "suspense": 4,
    "thriller": 8,
    "tokusatsu": 12,
    "tragedy": 39,
    "vampire": 16,
    "war": 37,
    "western": 45,
    "wuxia": 20,
    "youth": 24,
    "zombies": 28,
}


def _validate_top_filters(
    status: str, sort: str, response: Response
) -> tuple[int | None, str | None, dict | None]:
    st = _TOP_STATUS_CODES.get(status.lower())
    if st is None:
        response.status_code = 400
        return None, None, {
            "error": True,
            "code": 400,
            "description": f"Unknown status '{status}'. Supported values: {', '.join(_TOP_STATUS_CODES)}.",
        }

    so = sort.lower()
    if so not in _TOP_SORT_VALUES:
        response.status_code = 400
        return None, None, {
            "error": True,
            "code": 400,
            "description": f"Unknown sort '{sort}'. Supported values: {', '.join(_TOP_SORT_VALUES)}.",
        }

    return st, so, None


def _resolve_genres(genre: str | None, response: Response) -> tuple[str | None, dict | None]:
    """Parse a comma-separated genre string into a MDL ge= value. Returns (ge_value, error)."""
    if not genre:
        return None, None

    ids = []
    for raw in genre.split(","):
        key = raw.strip().lower().replace(" ", "_").replace("-", "_")
        gid = _TOP_GENRE_CODES.get(key)
        if gid is None:
            response.status_code = 400
            return None, {
                "error": True,
                "code": 400,
                "description": f"Unknown genre '{raw.strip()}'. Supported values: {', '.join(_TOP_GENRE_CODES)}.",
            }
        ids.append(str(gid))

    return ",".join(ids), None


def _build_top_query(
    co: int | None,
    st: int,
    so: str,
    page: int,
    ge: str | None,
    year_from: int | None,
    year_to: int | None,
    rating_min: float | None,
    rating_max: float | None,
) -> str:
    q = "search?adv=titles&ty=68"
    if co is not None:
        q += f"&co={co}"
    if ge:
        q += f"&ge={ge}"
    if year_from is not None or year_to is not None:
        q += f"&re={year_from or 1890},{year_to or 2026}"
    if rating_min is not None or rating_max is not None:
        q += f"&rt={rating_min or 0},{rating_max or 10}"
    q += f"&st={st}&so={so}&page={page}"
    return q


@app.get("/top")
async def fetch_top_all(
    response: Response,
    page: int = 1,
    status: str = "completed",
    sort: str = "top",
    genre: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    rating_min: float | None = None,
    rating_max: float | None = None,
) -> Dict[str, Any]:
    st, so, err = _validate_top_filters(status, sort, response)
    if err:
        return err

    ge, err = _resolve_genres(genre, response)
    if err:
        return err

    query = _build_top_query(None, st, so, page, ge, year_from, year_to, rating_min, rating_max)
    code, r = await fetch_func(query=query, t="top")

    response.status_code = code
    return r


@app.get("/top/{country}")
async def fetch_top(
    country: str,
    response: Response,
    page: int = 1,
    status: str = "completed",
    sort: str = "top",
    genre: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    rating_min: float | None = None,
    rating_max: float | None = None,
) -> Dict[str, Any]:
    co = _TOP_COUNTRY_CODES.get(country.lower())
    if co is None:
        response.status_code = 400
        return {
            "error": True,
            "code": 400,
            "description": f"Unknown country '{country}'. Supported values: {', '.join(_TOP_COUNTRY_CODES)}.",
        }

    st, so, err = _validate_top_filters(status, sort, response)
    if err:
        return err

    ge, err = _resolve_genres(genre, response)
    if err:
        return err

    query = _build_top_query(co, st, so, page, ge, year_from, year_to, rating_min, rating_max)
    code, r = await fetch_func(query=query, t="top")

    response.status_code = code
    return r


@app.get("/tags/search")
async def tags_search(q: str, response: Response) -> Any:
    client = cloudscraper.create_scraper()
    resp = client.get(
        "https://mydramalist.com/v1/tags/search",
        params={"lang": "en-US", "q": q, "approved": "true"},
    )
    response.status_code = resp.status_code
    return resp.json()


@app.get("/id/{drama_id}/threads")
async def fetch_threads(
    drama_id: str,
    response: Response,
    page: int = 1,
    limit: int = 50,
    sort: str = "recent",
    after: int | None = None,
) -> Any:
    # extract numeric id from slug (e.g. "687393-the-prisoner-of-beauty" -> "687393")
    numeric_id = drama_id.split("-")[0]

    params: Dict[str, Any] = {
        "t": numeric_id,
        "c": "title",
        "limit": limit,
        "page": page,
        "sort": sort,
        "lang": "en-US",
    }
    if after is not None:
        params["after"] = after

    client = cloudscraper.create_scraper()
    resp = client.get("https://mydramalist.com/v1/threads", params=params)

    response.status_code = resp.status_code
    return resp.json()


# get seasonal drama list -- official api available, use it with cloudflare bypass
@app.get("/seasonal/{year}/{quarter}")
async def mdlSeasonal(year: int, quarter: int) -> Any:
    # year -> ex. ... / 2019 / 2020 / 2021 / ...
    # quarter -> every 3 months (Jan-Mar=1, Apr-Jun=2, Jul-Sep=3, Oct-Dec=4)
    # --- seasonal information --- winter --- spring --- summer --- fall ---

    client = cloudscraper.create_scraper()

    return client.post(
        "https://mydramalist.com/v1/quarter_calendar",
        data={"quarter": quarter, "year": year},
    ).json()
