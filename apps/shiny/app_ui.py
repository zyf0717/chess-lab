import shinyswatch
from shiny import ui
from shinyswatch import theme_picker_ui

app_ui = ui.page_fluid(
    ui.tags.style(
        """
        /* Make the sidebar independently scrollable */
        .sidebar {
            max-height: 100vh;
            overflow-y: auto;
            position: sticky;
            top: 0;
            background: inherit;
        }

        .move-table td[data-ply] {
            cursor: pointer;
        }

        .move-table td.is-selected {
            background-color: var(--bs-primary-bg-subtle, #e6eefb);
            color: var(--bs-body-color, inherit);
            box-shadow: inset 0 0 0 2px var(--bs-primary, #0d6efd);
        }

        .move-table td[data-ply]:hover {
            background-color: var(--bs-secondary-bg, rgba(0, 0, 0, 0.05));
        }

        [data-bs-theme="dark"] .move-table td.is-selected,
        .bslib-dark .move-table td.is-selected {
            background-color: transparent;
            box-shadow: inset 0 0 0 2px rgba(110, 168, 254, 0.85);
        }

        [data-bs-theme="dark"] .move-table td[data-ply]:hover,
        .bslib-dark .move-table td[data-ply]:hover {
            background-color: rgba(13, 110, 253, 0.2);
        }
        """
    ),
    ui.tags.script(
        """
        document.addEventListener("click", (event) => {
            const cell = event.target.closest("td[data-ply]");
            if (!cell) return;

            const table = cell.closest("table");
            if (table) {
                table.querySelectorAll("td.is-selected").forEach((td) => {
                    td.classList.remove("is-selected");
                });
            }

            cell.classList.add("is-selected");
            const ply = parseInt(cell.dataset.ply, 10);
            if (Number.isNaN(ply)) return;

            if (window.Shiny && Shiny.setInputValue) {
                Shiny.setInputValue("move_cell", { ply: ply }, { priority: "event" });
            }
        });
        """
    ),
    ui.navset_bar(
        ui.nav_panel(
            "Analysis",
            ui.page_sidebar(
                ui.sidebar(
                    ui.input_file("pgn_upload", "Upload PGN:", accept=[".pgn", ".txt"]),
                    ui.input_text_area(
                        "pgn_text",
                        "Or paste PGN:",
                        rows=8,
                    ),
                    ui.input_action_button("analyze", "Analyse"),
                    ui.hr(),
                    theme_picker_ui(),
                ),
                ui.row(
                    ui.column(
                        8,
                        ui.card(
                            ui.card_header("Board"),
                            ui.div(ui.output_ui("board_view"), class_="text-center"),
                            ui.div(
                                ui.input_action_button("first_move", "<<"),
                                ui.input_action_button("prev_move", "<"),
                                ui.input_action_button("next_move", ">"),
                                ui.input_action_button("last_move", ">>"),
                                class_="d-flex justify-content-center gap-2 mt-2",
                            ),
                        ),
                    ),
                    ui.column(
                        4,
                        ui.card(
                            ui.card_header("Moves"),
                            ui.output_ui("move_list"),
                        ),
                    ),
                ),
            ),
        ),
        ui.nav_panel(
            "Library",
            ui.page_sidebar(
                ui.sidebar(
                    ui.p("Coming soon."),
                ),
                ui.card(
                    ui.card_header("Saved Games"),
                    ui.p("Browse saved PGNs here."),
                ),
            ),
        ),
        title="Chess Lab",
    ),
    theme=shinyswatch.theme.flatly,
)
