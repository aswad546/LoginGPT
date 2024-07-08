console.log("text-invisible.js: execution started");

window.addEventListener("load", () => {
    const style = document.createElement("style");
    style.innerText = "*:not(svg, svg *) { color: transparent !important; }";
    document.head.appendChild(style);
});

console.log("text-invisible.js: execution finished");
