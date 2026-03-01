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
    "chinese": 2,
}

_TOP_STATUS_CODES: Dict[str, int] = {
    "ongoing": 1,
    "upcoming": 2,
    "completed": 3,
}

_TOP_SORT_VALUES = {"top", "popular"}


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


@app.get("/top")
async def fetch_top_all(
    response: Response,
    page: int = 1,
    status: str = "completed",
    sort: str = "top",
) -> Dict[str, Any]:
    st, so, err = _validate_top_filters(status, sort, response)
    if err:
        return err

    query = f"search?adv=titles&ty=68&st={st}&so={so}&page={page}"
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

    query = f"search?adv=titles&ty=68&co={co}&st={st}&so={so}&page={page}"
    code, r = await fetch_func(query=query, t="top")

    response.status_code = code
    return r


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
