const inbcTracker = () => {
    console.log("[inbc-tracker]: execution started")

    /* LOG */

    window._inbc_log = (type, data) => {
        try {
            console.log(`[inbc-tracker]: ${type} | ${data}`)
            navigator.sendBeacon(`https://mock.sso-monitor.me/${type}`, JSON.stringify(data))
        }
        catch {}
    }

    /* FRAGMENT */

    window.addEventListener("load", () => {
        if (location.hash) {
            const fragment = {
                date: new Date(),
                documentLocation: document.location,
                documentTitle: document.title,
                data: location.hash.split("#")[1]
            }
            window._inbc_log("fragment", fragment)
        }
    })

    window.addEventListener("hashchange", () => {
        if (location.hash) {
            const fragment = {
                date: new Date(),
                documentLocation: document.location,
                documentTitle: document.title,
                data: location.hash.split("#")[1]
            }
            window._inbc_log("fragment", fragment)
        }
    })

    /* POSTMESSAGE */

    window.addEventListener("message", (e) => {
        const postmessage = {
            date: new Date(),
            origin: e.origin,
            documentLocation: document.location,
            documentTitle: document.title,
            data: e.data
        }
        window._inbc_log("postmessage", postmessage)
    })

    /* CHANNEL MESSAGING */

    // unpack "data" property of channel message's MessageEvent
    function unpackChannelMessageEvent(e) {
        return {
            isTrusted: e.isTrusted,
            bubbles: e.bubbles,
            cancelBubble: e.cancelBubble,
            cancelable: e.cancelable,
            composed: e.composed,
            currentTarget: e.currentTarget,
            data: e.data.data, // unpack
            defaultPrevented: e.defaultPrevented,
            eventPhase: e.eventPhase,
            lastEventId: e.lastEventId,
            origin: e.origin,
            ports: e.ports,
            returnValue: e.returnValue,
            source: e.source,
            srcElement: e.srcElement,
            target: e.target,
            timeStamp: e.timeStamp,
            type: e.type,
            userActivation: e.userActivation
        }
    }

    // https://developer.mozilla.org/en-US/docs/Web/API/MessagePort/postMessage
    MessagePort.prototype._postMessage = MessagePort.prototype.postMessage
    MessagePort.prototype.postMessage = function postMessage(message, transferList) {
        const channelmessage = {
            date: new Date(),
            origin: location.origin,
            data: message
        }
        return this._postMessage(channelmessage, transferList)
    }

    // https://developer.mozilla.org/en-US/docs/Web/API/MessagePort/start
    MessagePort.prototype._start = MessagePort.prototype.start
    MessagePort.prototype.start = function start() {
        this._started = true
        // pass cached messages to onmessage
        if (this._onmessage && !this._closed)
            (this._cached || []).forEach((msg) => { this._onmessage(msg) })
        // pass cached messages to listeners
        if (!this._closed)
            (this._cached || []).forEach((msg) => {
                (this._listeners || []).forEach((cb) => { cb(msg) })
            })
        // clear cache
        this._cached = []
    }

    // https://developer.mozilla.org/en-US/docs/Web/API/MessagePort/close
    MessagePort.prototype._close = MessagePort.prototype.close
    MessagePort.prototype.close = function close() {
        this._closed = true
        this._close()
    }

    // https://developer.mozilla.org/en-US/docs/Web/API/MessagePort/message_event
    MessagePort.prototype._addEventListener = MessagePort.prototype.addEventListener
    MessagePort.prototype.addEventListener = function addEventListener(type, listener) {
        if (type !== "message")
            return this._addEventListener(type, listener)
        if (!this._listeners)
            this._listeners = []
        this._listeners.push(listener)
    }

    // https://developer.mozilla.org/en-US/docs/Web/API/MessagePort/message_event
    Object.defineProperty(MessagePort.prototype, "onmessage", {
        set: function (cb) {
            this._onmessage = cb
            this.start()
        },
        get: function () { return this._onmessage }
    })

    // https://developer.mozilla.org/en-US/docs/Web/API/MessageChannel
    window._MessageChannel = window.MessageChannel
    window.MessageChannel = function MessageChannel() {
        const channel = new window._MessageChannel()

        // intercept all messages on port1 created via channel
        channel.port1._addEventListener("message", (e) => {
            const ee = unpackChannelMessageEvent(e) // unpack
            const channelmessage = {
                ...e.data,
                documentLocation: document.location,
                documentTitle: document.title
            }
            window._inbc_log("channelmessage", channelmessage)
            // pass message to listeners
            if (channel.port1._started && !channel.port1._closed)
                (channel.port1._listeners || []).forEach((cb) => { cb(ee) })
            // cache message on port
            else if (!channel.port1._started && !channel.port1._closed)
                if (!channel.port1._cached)
                    channel.port1._cached = []
                channel.port1._cached.push(ee)
            // pass message to onmessage
            if (channel.port1._onmessage && !channel.port1._closed)
                channel.port1._onmessage(ee)
        })
        channel.port1._start()

        // intercept all messages on port2 created via channel
        channel.port2._addEventListener("message", (e) => {
            const ee = unpackChannelMessageEvent(e) // unpack
            const channelmessage = {
                ...e.data,
                documentLocation: document.location,
                documentTitle: document.title
            }
            window._inbc_log("channelmessage", channelmessage)
            // pass message to listeners
            if (channel.port2._started && !channel.port2._closed)
                (channel.port2._listeners || []).forEach((cb) => { cb(ee) })
            // cache message on port
            else if (!channel.port2._started && !channel.port2._closed)
                if (!channel.port2._cached)
                    channel.port2._cached = []
                channel.port2._cached.push(ee)
            // pass message to onmessage
            if (channel.port2._onmessage && !channel.port2._closed)
                channel.port2._onmessage(ee)
        });
        channel.port2._start()
        return channel
    }

    // intercept all messages on port received via postmessage
    window.addEventListener("message", (e) => {
        for (const port of e.ports) {
            port._addEventListener("message", (e) => {
                const ee = unpackChannelMessageEvent(e) // unwrap
                const channelmessage = {
                    ...e.data,
                    documentLocation: document.location,
                    documentTitle: document.title
                }
                window._inbc_log("channelmessage", channelmessage)
                // pass message to listeners
                if (port._started && !port._closed)
                    (port._listeners || []).forEach((cb) => { cb(ee) })
                // cache message on port
                else if (!port._started && !port._closed)
                    if (!port._cached)
                        port._cached = []
                    port._cached.push(ee)
                // pass message to onmessage
                if (port._onmessage && !port._closed)
                    port._onmessage(ee)
            })
            port._start()
        }
    });

    console.log("[inbc-tracker]: execution finished")
}

const inbcTrackerScript = "(" + inbcTracker.toString() + ")()"
const script = document.createElement("script")
script.setAttribute("type", "text/javascript")
script.appendChild(document.createTextNode(inbcTrackerScript))
document.documentElement.appendChild(script)
