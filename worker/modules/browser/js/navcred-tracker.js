console.log("navcred-tracker.js: execution started");

/**
 * Make credential objects JSON serializable.
 * - https://developer.mozilla.org/en-US/docs/Web/API/Credential
 */

// https://developer.mozilla.org/en-US/docs/Web/API/PasswordCredential
PasswordCredential.prototype.toJSON = function() {
    return {
        id: this.id,
        type: this.type,
        name: this.name,
        iconURL: this.iconURL,
        password: this.password
    }
}

// https://developer.mozilla.org/en-US/docs/Web/API/FederatedCredential
FederatedCredential.prototype.toJSON = function() {
    return {
        id: this.id,
        type: this.type,
        name: this.name,
        iconURL: this.iconURL,
        provider: this.provider,
        protocol: this.protocol
    }
}

// https://developer.mozilla.org/en-US/docs/Web/API/IdentityCredential
IdentityCredential.prototype.toJSON = function() {
    return {
        id: this.id,
        type: this.type,
        token: this.token
    }
}

// https://developer.mozilla.org/en-US/docs/Web/API/PublicKeyCredential
PublicKeyCredential.prototype.toJSON = function() {
    return {
        id: this.id,
        type: this.type,
        rawId: this.rawId,
        response: this.response,
        authenticatorAttachment: this.authenticatorAttachment
    }
}

/**
 * Wrap navigator.credentials methods to track their arguments.
 * - https://developer.mozilla.org/en-US/docs/Web/API/CredentialsContainer
 * - https://web.dev/security-credential-management/
 * - https://blog.sentry.io/wrap-javascript-functions/
 */

window._ssomon_navigator_credentials_create = navigator.credentials.create
navigator.credentials.create = function create(...args) {
    try {
        console.log(`navcred-tracker.js: navigator.credentials.create(${JSON.stringify(args)})`)
        if (window._ssomon_navcred_callback) window._ssomon_navcred_callback("create", JSON.parse(JSON.stringify(args)))
    } catch (error) {
        console.error(error)
    }
    return window._ssomon_navigator_credentials_create.apply(navigator.credentials, args)
}

window._ssomon_navigator_credentials_get = navigator.credentials.get
navigator.credentials.get = function get(...args) {
    try {
        console.log(`navcred-tracker.js: navigator.credentials.get(${JSON.stringify(args)})`)
        if (window._ssomon_navcred_callback) window._ssomon_navcred_callback("get", JSON.parse(JSON.stringify(args)))
    } catch (error) {
        console.error(error)
    }
    return window._ssomon_navigator_credentials_get.apply(navigator.credentials, args)
}

window._ssomon_navigator_credentials_preventSilentAccess = navigator.credentials.preventSilentAccess
navigator.credentials.preventSilentAccess = function preventSilentAccess(...args) {
    try {
        console.log(`navcred-tracker.js: navigator.credentials.preventSilentAccess(${JSON.stringify(args)})`)
        if (window._ssomon_navcred_callback) window._ssomon_navcred_callback("preventSilentAccess", JSON.parse(JSON.stringify(args)))
    } catch (error) {
        console.error(error)
    }
    return window._ssomon_navigator_credentials_preventSilentAccess.apply(navigator.credentials, args)
}

window._ssomon_navigator_credentials_store = navigator.credentials.store
navigator.credentials.store = function store(...args) {
    try {
        console.log(`navcred-tracker.js: navigator.credentials.store(${JSON.stringify(args)})`)
        if (window._ssomon_navcred_callback) window._ssomon_navcred_callback("store", JSON.parse(JSON.stringify(args)))
    } catch (error) {
        console.error(error)
    }
    return window._ssomon_navigator_credentials_store.apply(navigator.credentials, args)
}

console.log("navcred-tracker.js: execution finished");
