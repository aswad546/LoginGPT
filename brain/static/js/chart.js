Chart.defaults.plugins.title.font = {size: 22, family: "Avenir, Helvetica, Arial, sans-serif"}
Chart.defaults.plugins.title.color = "black"
Chart.defaults.plugins.subtitle.font = {size: 16, family: "Avenir, Helvetica, Arial, sans-serif"}
Chart.defaults.plugins.subtitle.color = "black"
Chart.defaults.plugins.legend.position = "bottom"
Chart.defaults.maintainAspectRatio = true

COLORS = {
    red: "#dc3545",
    blue: "#0d6efd",
    yellow: "#ffc107",
    green: "#198754",
    indigo: "#6610f2",
    orange: "#fd7e14",
    purple: "#6f42c1",
    pink: "#d63384",
    teal: "#20c997",
    cyan: "#0dcaf0",
    gray: "#adb5bd",
    black: "#000000"
}

const renderChart = ({
    element = undefined,
    masonry = undefined,
    type = "pie",
    labels = [],
    datasets = [],
    title = "",
    subtitle = "",
    options = {}
} = {}) => {

    // context
    const ctx = document.createElement("div")
    ctx.className = "bg-light rounded-3 m-2"

    // canvas
    const cvs = document.createElement("canvas")
    cvs.id = uuidv4()

    // default colors
    for (let i = 0; i < datasets.length; i++) {
        if (type == "pie" && !datasets[i].backgroundColor) {
            datasets[i].backgroundColor = Object.values(COLORS)
        }
    }
    for (let i = 0; i < datasets.length; i++) {
        if (type != "pie" && !datasets[i].backgroundColor) {
            datasets[i].backgroundColor = Object.values(COLORS)[i]
        }
    }

    // enlarge modal
    const btnenlarge = document.createElement("button")
    btnenlarge.className = "btn btn-sm btn-outline-secondary m-2"
    btnenlarge.innerHTML = `<i class="bi bi-fullscreen"></i> Enlarge`
    btnenlarge.onclick = () => {
        const modal = document.createElement("div")
        modal.className = "modal fade"
        modal.id = uuidv4()
        modal.setAttribute("cid", uuidv4())
        modal.tabIndex = -1
        modal.innerHTML = `
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">${title}</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                <div class="modal-body">
                    <canvas id="${modal.getAttribute('cid')}"></canvas>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-primary" onclick="(() => {
                        const link = document.createElement('a')
                        link.download = 'chart.png'
                        link.href = document.getElementById('${modal.getAttribute('cid')}').toDataURL()
                        link.click()
                    })()"><i class="bi bi-download"></i> Download</button>
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                </div>
            </div>
        `
        document.body.appendChild(modal)
        const modalInstance = new bootstrap.Modal(modal)
        modalInstance.show()
        const chart = new Chart(document.getElementById(modal.getAttribute("cid")), {
            type: type,
            data: {
                labels: labels,
                datasets: datasets
            },
            options: {
                plugins: {
                    title: {
                        display: true,
                        text: title
                    },
                    subtitle: {
                        display: true,
                        text: subtitle
                    },
                    legend: {
                        display: true
                    }
                },
                responsive: true,
                ...options
            }
        })
        modal.addEventListener("hidden.bs.modal", () => {
            chart.destroy()
            modal.remove()
        })
    }

    // insert context
    ctx.appendChild(btnenlarge)
    ctx.appendChild(cvs)
    if (element) element.appendChild(ctx)
    if (masonry) {
        masonry.appended(ctx)
        masonry.layout()
    }

    new Chart(cvs, {
        type: type,
        data: {
            labels: labels,
            datasets: datasets
        },
        options: {
            plugins: {
                title: {
                    display: true,
                    text: title
                },
                subtitle: {
                    display: true,
                    text: subtitle
                },
                legend: {
                    display: false
                }
            },
            responsive: false,
            ...options
        }
    })

}
