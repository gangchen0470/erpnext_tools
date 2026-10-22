frappe.pages["tools"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Tools"),
		single_column: true,
	});

	const $root = $("<div class='tools-home'></div>").appendTo(page.body);

	if (frappe.user_roles.includes("System Manager") || frappe.user_roles.includes("Tools Manager")) {
		page.add_inner_button(__("Manage Tools"), () => frappe.set_route("List", "Tool Definition"));
		page.add_inner_button(__("Manage Categories"), () => frappe.set_route("List", "Tool Category"));
	}

	frappe.call("tools.api.get_tools").then(({ message = [] }) => render_tools($root, message));
};

function render_tools($root, tools) {
	$root.empty();
	if (!tools.length) {
		$("<div class='tools-empty text-muted'></div>")
			.text(__("No tools are available for your roles yet."))
			.appendTo($root);
		return;
	}

	const groups = {};
	tools.forEach((tool) => (groups[tool.category || __("General")] ||= []).push(tool));

	Object.entries(groups).forEach(([category, items]) => {
		const $section = $("<section class='tools-section'></section>").appendTo($root);
		$("<h3 class='tools-category'></h3>").text(category).appendTo($section);
		const $grid = $("<div class='tools-grid'></div>").appendTo($section);

		items.forEach((tool) => {
			const $card = $("<button type='button' class='tools-card'></button>").appendTo($grid);
			const $icon = $("<span class='tools-card-icon'></span>").appendTo($card);
			$icon.css("--tool-color", tool.color || "var(--blue-500)");
			$icon.append(frappe.utils.icon(tool.icon || "tool", "md"));
			const $copy = $("<span class='tools-card-copy'></span>").appendTo($card);
			$("<strong></strong>").text(tool.title).appendTo($copy);
			$("<small></small>").text(tool.description || "").appendTo($copy);

			$card.on("click", () => {
				if (tool.route_type === "External URL" || tool.open_in_new_tab) {
					window.open(tool.route, "_blank", "noopener,noreferrer");
				} else {
					window.location.assign(tool.route);
				}
			});
		});
	});
}
