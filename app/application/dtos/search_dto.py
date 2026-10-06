from pydantic import BaseModel


class SearchItemDTO(BaseModel):
    title: str
    subtitle: str
    link: str


class SearchGroupDTO(BaseModel):
    key: str
    label: str
    total: int  # correspondências no banco (a lista traz no máximo `per_group`)
    items: list[SearchItemDTO]


class SearchResultDTO(BaseModel):
    query: str
    groups: list[SearchGroupDTO]  # apenas grupos com resultado
