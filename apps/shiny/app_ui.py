import shinyswatch
from shiny import ui
from shinyswatch import theme_picker_ui

app_ui = ui.page_fluid(
    ui.tags.style(
        """
        :root {
            --board-size: 360px;
        }

        /* Make the sidebar independently scrollable */
        .sidebar {
            max-height: 100vh;
            overflow-y: auto;
            position: sticky;
            top: 0;
            background: inherit;
        }

        .board-frame {
            min-height: var(--board-size);
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .move-table-wrap {
            max-height: var(--board-size);
            overflow-y: auto;
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

        .fen-line {
            word-break: break-all;
        }

        .fen-line code {
            word-break: break-all;
        }

        .prev-pv-line {
            font-size: 0.9rem;
        }

        line.arrow {
            opacity: 0.7;
        }

        polygon.arrow {
            opacity: 0.7;
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
        const scrollSelectedIntoView = () => {
            const container = document.getElementById("move_table_container");
            if (!container) return;
            const selected = container.querySelector("td.is-selected");
            if (!selected) return;
            const selectedRect = selected.getBoundingClientRect();
            const containerRect = container.getBoundingClientRect();
            if (selectedRect.top < containerRect.top || selectedRect.bottom > containerRect.bottom) {
                selected.scrollIntoView({ block: "nearest" });
            }
        };

        const observeMoveTable = () => {
            const container = document.getElementById("move_table_container");
            if (!container || container._observerAttached) return;
            const observer = new MutationObserver(() => scrollSelectedIntoView());
            observer.observe(container, { childList: true, subtree: true });
            container._observerAttached = true;
        };

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

            scrollSelectedIntoView();
        });

        document.addEventListener("DOMContentLoaded", observeMoveTable);
        document.addEventListener("shiny:connected", observeMoveTable);
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
                    ui.input_select(
                        "multipv",
                        "Engine lines",
                        choices=[str(value) for value in range(1, 9)],
                        selected="3",
                    ),
                    ui.input_select(
                        "think_time",
                        "Engine time (seconds)",
                        choices=["1", "3", "10"],
                        selected="1",
                    ),
                    ui.input_action_button("annotate_moves", "Annotate Game"),
                    ui.hr(),
                    theme_picker_ui(),
                ),
                ui.row(
                    ui.column(
                        12,
                        ui.card(
                            ui.card_header("Game Info"),
                            ui.output_ui("game_info"),
                        ),
                    ),
                    ui.column(
                        8,
                        ui.card(
                            ui.card_header("Board"),
                            ui.div(ui.output_ui("board_view"), class_="board-frame"),
                            ui.div(
                                ui.input_action_button("first_move", "<<"),
                                ui.input_action_button("prev_move", "<"),
                                ui.input_action_button("next_move", ">"),
                                ui.input_action_button("last_move", ">>"),
                                class_="d-flex justify-content-center gap-2 mt-2",
                            ),
                            ui.output_ui("fen_line"),
                            ui.output_text("eval_line"),
                            ui.output_ui("pv"),
                            ui.output_ui("prev_pv"),
                        ),
                    ),
                    ui.column(
                        4,
                        ui.card(
                            ui.card_header("Moves"),
                            ui.div(
                                ui.output_ui("move_list"),
                                id="move_table_container",
                                class_="move-table-wrap",
                            ),
                        ),
                        ui.card(
                            ui.card_header("Move Summary"),
                            ui.output_ui("move_summary"),
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
