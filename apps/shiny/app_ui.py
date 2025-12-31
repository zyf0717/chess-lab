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
                            ui.output_data_frame("move_list"),
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
