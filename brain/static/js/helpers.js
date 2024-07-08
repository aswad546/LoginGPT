const timestampToString = (t) => {
    if (!t) return "N/A"
    const date = new Date(t*1000)
    return date.toLocaleString()
}

const uuidv4 = () => {
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
        const r = Math.random()*16|0, v = c == "x" ? r : (r&0x3|0x8)
        return v.toString(16)
    })
}

const iconClassFromIdp = (idp) => {
    switch (idp) {
        case "GOOGLE":
            return "bi-google"
        case "FACEBOOK":
            return "bi-facebook"
        case "APPLE":
            return "bi-apple"
        case "MICROSOFT":
            return "bi-microsoft"
        case "TWITTER":
            return "bi-twitter"
        case "TWITTER_1.0":
            return "bi-twitter"
        case "TWITTER_2.0":
            return "bi-twitter"
        case "LINKEDIN":
            return "bi-linkedin"
        case "QQ":
            return "bi-tencent-qq"
        case "SINA_WEIBO":
            return "bi-sina-weibo"
        case "WECHAT":
            return "bi-wechat"
        case "GITHUB":
            return "bi-github"
        default:
            return "bi-question-circle"
    }
}

const iconClassFromAnalysis = (analysis) => {
    switch(analysis) {
        case "landscape_analysis":
            return "bi-globe"
        case "login_trace_analysis":
            return "bi-box-arrow-in-right"
        case "wildcard_receiver_analysis":
            return "bi-asterisk"
        default:
            return "bi-question-circle"
    }
}

const iconClassFromLpcStrategy = (lpcStrategy) => {
    switch (lpcStrategy) {
        case "MANUAL":
            return "bi-pencil"
        case "SEARCH_ENGINES":
            return "bi-search"
        case "METASEARCH":
            return "bi-search"
        case "PATHS":
            return "bi-slash-square"
        case "HOMEPAGE":
            return "bi-house"
        case "CRAWLING":
            return "bi-regex"
        case "ROBOTS":
            return "bi-robot"
        case "SITEMAP":
            return "bi-diagram-3"
        default:
            return "bi-question-circle"
    }
}
