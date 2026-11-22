# Frontend Changes

## Clients page: CRUD and payment-risk panel

**Files changed or created**
- `src/services/api.js`: added `createClient`, `updateClient`, `deleteClient` after `getClientPaymentRisk`. Existing exports unchanged.
- `src/components/ClientFormModal.jsx` (new): add/edit modal with Name, Email, Phone, Company and Notes fields, client-side validation and API error mapping.
- `src/components/ConfirmDialog.jsx` (new): reusable confirm dialog with busy and error states.
- `src/pages/Clients.jsx`: "+ Add Client" button, Actions column (Edit, Delete), success notices, delete flow, and reload after mutations. The table, empty state, loading state, row selection and payment-risk panel are kept.

**API helpers added**
- `createClient(data)`: `POST /clients`
- `updateClient(id, data)`: `PUT /clients/{id}`
- `deleteClient(id)`: `DELETE /clients/{id}`

**User actions**
- Add: "+ Add Client" opens the form in create mode. A new client is not auto-selected.
- Edit: the row's "Edit" button opens the form pre-filled. After saving, the payment-risk panel shows the updated client.
- Delete: the row's "Delete" button opens a confirmation. Confirming deletes the client; if it was selected, the selection is cleared.
- Row clicks still select a client; the Edit and Delete buttons do not change the selection.

**Error handling**
- 409 email already in use: shown under the Email field.
- 409 delete when the client has invoices: the backend message is shown in the delete dialog, and the client is not deleted.
- 404: create and edit errors are shown on the form. On delete, "This client no longer exists." is shown and the list reloads.
- 422: validation messages from the backend are shown at form level.
- Network failure: "Could not reach the API. Check that the backend is running."
- Reload failure after a mutation: "Unable to refresh clients. Check backend connection."

**How to test**
1. Run `npm run dev` in `frontend/` (with the backend running).
2. Click "+ Add Client", leave Name empty and confirm "Name is required." appears. Add a client with a name.
3. Click "Edit" on a client, change a field, and save. Confirm "Client updated." appears.
4. Try deleting a client that has invoices and confirm the 409 message appears in the dialog.
5. Delete a client without invoices and confirm "Client deleted." appears.
6. Click a row and confirm the payment-risk panel appears at the bottom.

Note: the backend was not modified.
