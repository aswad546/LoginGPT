const api = {

    endpoint: `${location.origin}/api`,

    call: (path, method="GET", headers=undefined, body=undefined, showProgress=true) => {
        if (pushProgress && showProgress) pushProgress()
        return new Promise((resolve, reject) => {
            let options = {method}
            if (headers !== undefined) options["headers"] = headers
            if (body !== undefined) options["body"] = body
            fetch(`${api.endpoint}${path}`, options).then(r => {
                if (r.status == 200) return r
                else reject({success: false, error: `Received response with status code ${r.status}`, data: null})
            }).then(r => {
                return r.json()
            }).then(r => {
                if (popProgress) popProgress()
                if (r["success"]) resolve(r)
                else reject(r)
            }).catch(e => {
                if (popProgress) popProgress()
                reject({success: false, error: `${e}`, data: null})
            })
        })
    },

    /* admin */

    showTopSitesLists: () => {
        return api.call("/admin/top_sites_lists")
    },

    uploadTopSitesList: (id, file, rankFileIdx, domainFileIdx) => {
        const formData = new FormData()
        formData.append("list_file", file)
        return api.call(`/admin/top_sites_lists?list_id=${id}&list_rank_index=${rankFileIdx}&list_domain_index=${domainFileIdx}`, method="PUT", body=formData)
    },

    deleteTopSitesList: (id) => {
        return api.call(`/admin/top_sites_lists?list_id=${id}`, method="DELETE")
    },

    createDBIndex: () => {
        return api.call("/admin/db_index", method="POST")
    },

    dbQuery: (methodDb, collection, query, projection) => {
        return api.call(
            `/admin/db_query`,
            method="POST",
            headers={"Content-Type": "application/json"},
            body=JSON.stringify({method: methodDb, collection, query, projection})
        )
    },

    getQuery: () => {
        return api.call("/admin/query")
    },

    addQuery: (description, query) => {
        return api.call(`/admin/query?description=${description}&query=${query}`, method="PUT")
    },

    deleteQuery: (query) => {
        return api.call(`/admin/query?query=${query}`, method="DELETE")
    },

    copyGroundTruth: (sourceGtId, targetGtId) => {
        return api.call(`/admin/ground_truth/duplicate?source_gt_id=${sourceGtId}&target_gt_id=${targetGtId}`, method="POST")
    },

    deleteGroundTruth: (gtId) => {
        return api.call(`/admin/ground_truth?gt_id=${gtId}`, method="DELETE")
    },

    /* rabbit */

    rabbitPurgeQueue: (queue) => {
        return api.call(`/rabbit/queues/%252F/${queue}/contents`, method="DELETE")
    },

    /* scans */

    deleteScan: (scanID) => {
        return api.call(`/scans?scan_id=${scanID}`, method="DELETE")
    },

    scanIDs: (taskName) => {
        return api.call(`/scans/${taskName}/ids`, method="GET")
    },

    rescanErrors: (taskName, scanID) => {
        return api.call(`/scans/${taskName}/rescan?scan_id=${scanID}`, method="POST")
    },

    duplicates: (taskName, scanID) => {
        return api.call(`/scans/${taskName}/duplicates?scan_id=${scanID}`, method="GET")
    },

    deleteDuplicates: (taskName, scanID) => {
        return api.call(`/scans/${taskName}/duplicates?scan_id=${scanID}`, method="DELETE")
    },

    /* tags */

    tags: () => {
        return api.call(`/tags`, method="GET")
    },

    addScanTag: (scanID, tagName) => {
        return api.call(`/tags?scan_id=${scanID}&tag_name=${tagName}`, method="PUT")
    },

    deleteScanTag: (scanID, tagName) => {
        return api.call(`/tags?scan_id=${scanID}&tag_name=${tagName}`, method="DELETE")
    },

    /* list */

    getTrancoId: (date) => {
        return api.call(`/list/tranco_id?date=${date}`, method="GET", headers=undefined, body=undefined, showProgress=false)
    },

    /* tasks */

    runAnalysis: (type, data) => {
        return api.call(
            `/tasks/${type}/treq`,
            method="PUT",
            headers={"Content-Type": "application/json"},
            body=JSON.stringify(data)
        )
    },

    /* stats: gt */

    statsGt: (gtID) => {
        return api.call(`/stats/gt?gt_id=${gtID}`)
    },

    /* stats: loginpage */

    statsLoginpageCandidatesByStrategy: (scanID, tagName) => {
        let url = "/stats/loginpage/candidates_by_strategy"
        if (scanID) url += `?scan_id=${scanID}`
        if (tagName) url += `?tag_name=${tagName}`
        return api.call(url)
    },

    statsLoginpageConfirmedByIntegrationAndStrategy: (scanID, tagName) => {
        let url = "/stats/loginpage/confirmed_by_integration_and_strategy"
        if (scanID) url += `?scan_id=${scanID}`
        if (tagName) url += `?tag_name=${tagName}`
        return api.call(url)
    },

    statsLoginpageConfirmedByPathAndSubdomain: (scanID, tagName) => {
        let url = "/stats/loginpage/confirmed_by_paths_and_subdomains"
        if (scanID) url += `?scan_id=${scanID}`
        if (tagName) url += `?tag_name=${tagName}`
        return api.call(url)
    },

    statsLoginpageConfirmedByMetasearchInfo: (scanID, tagName) => {
        let url = "/stats/loginpage/confirmed_by_metasearch_info"
        if (scanID) url += `?scan_id=${scanID}`
        if (tagName) url += `?tag_name=${tagName}`
        return api.call(url)
    },

    /* stats: resolve */

    statsResolveResolvedDomainsAndErrors: (scanID, tagName) => {
        let url = "/stats/resolve/resolved_domains_and_errors"
        if (scanID) url += `?scan_id=${scanID}`
        if (tagName) url += `?tag_name=${tagName}`
        return api.call(url)
    },

    statsResolveResolvedDomainVsListDomain: (scanID, tagName) => {
        let url = "/stats/resolve/resolved_domain_vs_list_domain"
        if (scanID) url += `?scan_id=${scanID}`
        if (tagName) url += `?tag_name=${tagName}`
        return api.call(url)
    },

    statsResolveLoginPageDomainVsListDomain: (scanID, tagName) => {
        let url = "/stats/resolve/login_page_domain_vs_list_domain"
        if (scanID) url += `?scan_id=${scanID}`
        if (tagName) url += `?tag_name=${tagName}`
        return api.call(url)
    },

    /* stats: scans */

    statsScansTimeVsIdps: (tagNames, scanIDs) => {
        let url = "/stats/scans/time_vs_idps?"
        scanIDs.forEach(sid => url += `scan_id=${sid}&`)
        tagNames.forEach(tn => url += `tag_name=${tn}&`)
        return api.call(url)
    },

    /* stats: sso */

    statsSSO: (scanID, tagName) => {
        let url = "/stats/sso"
        if (scanID) url += `?scan_id=${scanID}`
        if (tagName) url += `?tag_name=${tagName}`
        return api.call(url)
    },

    statsSSOIdP: (scanID, tagName) => {
        let url = "/stats/sso/idp"
        if (scanID) url += `?scan_id=${scanID}`
        if (tagName) url += `?tag_name=${tagName}`
        return api.call(url)
    },

    statsSSORank: (scanID, tagName) => {
        let url = "/stats/sso/rank"
        if (scanID) url += `?scan_id=${scanID}`
        if (tagName) url += `?tag_name=${tagName}`
        return api.call(url)
    },

    statsSSOElementCoordinates: (scanID, tagName) => {
        let url = "/stats/sso/element_coordinates"
        if (scanID) url += `?scan_id=${scanID}`
        if (tagName) url += `?tag_name=${tagName}`
        return api.call(url)
    },

    statsSSOIntegration: (scanID, tagName) => {
        let url = "/stats/sso/integration"
        if (scanID) url += `?scan_id=${scanID}`
        if (tagName) url += `?tag_name=${tagName}`
        return api.call(url)
    },

    statsSSOFrame: (scanID, tagName) => {
        let url = "/stats/sso/frame"
        if (scanID) url += `?scan_id=${scanID}`
        if (tagName) url += `?tag_name=${tagName}`
        return api.call(url)
    },

    statsSSORecognitionStrategy: (scanID, tagName) => {
        let url = "/stats/sso/recognition_strategy"
        if (scanID) url += `?scan_id=${scanID}`
        if (tagName) url += `?tag_name=${tagName}`
        return api.call(url)
    },

    /* stats: wra */

    statsWra: (scanID) => {
        return api.call(`/stats/wra?scan_id=${scanID}`)
    },

}
