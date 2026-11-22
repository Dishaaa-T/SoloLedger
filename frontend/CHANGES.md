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

## Invoices page: management UI

- Files created: `src/components/InvoiceFormModal.jsx` creates and edits invoices with a client dropdown. It checks that the amount is greater than 0 and that the due date is not before the issue date. A duplicate invoice number is shown from the 409 response.
- Files created: `src/components/MarkPaidDialog.jsx` asks for the actual payment date. It checks that the date is not before the issue date and not in the future. It never marks an invoice paid automatically.
- Files created: `src/components/InvoiceDetailModal.jsx` shows read-only invoice details with Edit, Mark as paid and Delete actions.
- Files changed: `src/pages/Invoices.jsx` was rewritten. It shows summary cards for total count, total invoiced, paid, pending and overdue, computed from the fetched list. It has filter tabs for All, Paid, Pending and Overdue. The table is sorted newest first and uses status pills. Clicking a row opens the details. The Edit, Mark as paid and Delete actions are available, and Delete asks for confirmation.
- Files changed: `src/services/api.js` adds `createInvoice`, `updateInvoice`, `markInvoicePaid` and `deleteInvoice`. Existing exports are unchanged.
- Backend endpoints used: `POST /invoices`, `PUT /invoices/{id}`, `POST /invoices/{id}/mark-paid`, `DELETE /invoices/{id}`, `GET /invoices` and `GET /clients`. The update endpoint does not accept a status or payment date, so payments go only through mark-paid.
- Not changed: backend files, the ML payment-risk feature, the dashboard and other pages.
- How to test: run the backend and the frontend. On the Invoices page, create an invoice and try an amount of 0, a due date before the issue date, and a duplicate invoice number. Then edit it, mark it paid with a date, and delete a test invoice.

## Expenses page: management UI

- Files created: `src/components/ExpenseFormModal.jsx` is the add and edit form. It has title, description, amount (must be greater than 0), category, expense date, payment method, status, and notes. Status has an "Automatic (based on date)" option; when Automatic is chosen the status is left out of the request so the backend date rule applies. In edit mode a null status is never sent.
- Files created: `src/components/ExpenseDetailModal.jsx` shows read-only expense details with Edit and Delete actions.
- Files changed: `src/pages/Expenses.jsx` was rewritten. It shows summary cards for total, paid, upcoming and record count, computed from all fetched expenses. It has search by title or description, and status, category and date-range filters applied in the browser. The table is sorted newest first and uses status pills. Clicking a row opens the details. Edit and Delete actions are available, and Delete asks for confirmation.
- Files changed: `src/services/api.js` adds `getExpense` and `updateExpense`. Existing exports are unchanged.
- Category list: the form and filter use the defaults Software & Subscriptions, Internet & Utilities, Equipment, Travel, Marketing, Office Supplies, Professional Services and Other, plus any other categories found in the saved expenses.
- Backend endpoints used: `POST /expenses`, `GET /expenses`, `GET /expenses/{id}`, `PUT /expenses/{id}` and `DELETE /expenses/{id}`.
- Not changed: backend files, the cash balance, dashboard calculations, forecast, simulator, Action Centre, and the stray file `src/Expenses.jsx` (not imported by the app, left alone).
- How to test: run the backend and the frontend. On the Expenses page, add an expense with amount 0 (rejected) and one with a blank title (rejected). Add one with a paid status, one with an upcoming status, and one left on Automatic. Edit one and confirm the other fields are kept. Filter by category, status and dates. Delete a test expense.

