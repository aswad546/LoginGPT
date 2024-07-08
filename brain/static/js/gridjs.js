const gridjsDefaultStyle = {
    table: {
        "white-space": "nowrap"
    }
}

const gridjsDefaultServerPagination = {
    limit: 10,
    server: {
        url: (prev, page, limit) => {
            const url = new URL(prev.startsWith("/") ? `${location.origin}${prev}` : prev)
            url.searchParams.set("offset", page * limit)
            url.searchParams.set("limit", limit)
            return url.toString()
        }
    }
}

const gridjsDefaultStaticPagination = {
    limit: 10
}
