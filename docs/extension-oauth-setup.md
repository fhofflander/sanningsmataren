# Extension ID and Google sign-in (OAuth) setup

Prep for #10 (Google sign-in). Read this before configuring OAuth, because the
extension ID is a prerequisite and there is a common misconception about it.

## The extension ID cannot be chosen from code

For a **Chrome Web Store** item, Google assigns the extension ID when the item
is first created, derived from a key pair the store manages. You cannot pick it,
and the manifest `key` field does **not** set the published ID. The `key` field
only fixes the ID when loading the extension **unpacked locally**.

To make local development use the same ID as production, you copy the item's
public key from the Developer Dashboard into the manifest `key`. So the real
unblock for OAuth is creating the store item to obtain the production ID.

### Procedure to lock the ID

1. Zip the current `dist-extension/` build (icons already added in #8, so it is
   submittable) and **create the item as a draft** in the Developer Dashboard.
   You do not need to publish it.
2. From the item's page, copy its **public key** (Dashboard provides the `key`
   value).
3. Paste it into `manifest.json` as `"key": "<value>"`. Local dev now shares the
   production ID.
4. Note the assigned **extension ID**; you need it for the OAuth client below.

## Manifest changes for OAuth (apply when wiring #10)

```jsonc
{
  "permissions": ["activeTab", "contextMenus", "scripting", "sidePanel", "storage", "identity"],
  "oauth2": {
    "client_id": "[GOOGLE_OAUTH_CLIENT_ID].apps.googleusercontent.com",
    "scopes": ["openid", "email", "profile"]
  },
  "key": "[PUBLIC KEY FROM DASHBOARD]"
}
```

The backend-domain host permission that replaces the three provider hosts is
tracked separately in #9.

## Google Cloud Console steps

1. Create or pick a Google Cloud project.
2. **OAuth consent screen:** External. App name, support email, logo optional.
   Scopes = `openid`, `email`, `profile` only. These are **non-sensitive**, so
   no separate Google verification or brand review is triggered. Add yourselves
   as test users while the screen is in Testing.
3. **Credentials → Create OAuth client ID → Application type "Chrome app"**
   (a.k.a. Chrome Extension). Enter the extension ID from the step above. This
   produces the `client_id` for the manifest.

## Keep scopes non-sensitive

Requesting only `openid email profile` keeps you in the fast lane. The moment a
**sensitive** scope is added, Google runs its own multi-week verification,
entirely separate from the Chrome Web Store review. Do not add scopes you do not
need.

## Auth flow (recap of #10)

- Recommended: `chrome.identity.launchWebAuthFlow` with `response_type=id_token`
  and a nonce, so the backend verifies the JWT offline against Google's public
  keys. No extra round trip.
- Alternative: `chrome.identity.getAuthToken` (access token) plus a call to
  Google's `userinfo` endpoint.

## Action items

- [ ] **You/Fredrik:** create the draft store item to obtain the production ID
- [ ] **You/Fredrik:** create the Google Cloud OAuth client (type "Chrome app")
      bound to that ID, scopes `openid email profile`
- [ ] **Fredrik:** implement the chosen `chrome.identity` flow + backend token
      verification (#10)
- [ ] **Later:** add `identity`, `oauth2`, `key`, and the backend host to the
      manifest
