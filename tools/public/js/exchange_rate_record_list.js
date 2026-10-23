frappe.listview_settings["Exchange Rate Record"] = {
  onload(listview) {
    if (!frappe.user_roles.includes("System Manager") &&
        !frappe.user_roles.includes("Tools Manager") &&
        !frappe.user_roles.includes("Accounts Manager")) return;

    listview.page.add_inner_button(__("Fetch Latest Rates"), () => {
      frappe.call({
        method: "tools.exchange_rates.sync_rates",
        freeze: true,
        freeze_message: __("Fetching exchange rates from configured API..."),
      }).then((r) => {
        const message = r.message || {};
        const successes = message.success || [];
        const failures = message.failed || [];
        frappe.msgprint({
          title: __("Exchange Rate Sync"),
          indicator: failures.length ? "orange" : "green",
          message: __("{0} pair(s) succeeded; {1} pair(s) failed.", [successes.length, failures.length]) +
            (failures.length ? "<br><br>" + failures.map(x => frappe.utils.escape_html(x.pair + ": " + x.error)).join("<br>") : ""),
        });
        listview.refresh();
      });
    });

    listview.page.add_inner_button(__("Exchange Rate Settings"), () => {
      frappe.set_route("Form", "Exchange Rate Settings", "Exchange Rate Settings");
    });
  }
};
