import shinyswatch
from shiny import ui
from shinyswatch import theme_picker_ui
from shinywidgets import output_widget

# CSS for sticky sidebars and independent scrolling
CUSTOM_CSS = """
    .sidebar {
        max-height: calc(100vh - 56px);
        overflow-y: auto;
        position: sticky;
        top: 56px;
        background: inherit;
    }

    :root {
        --board-size: 360px;
        --board-card-max-height: calc(var(--board-size) + 8.5rem);
    }

    .analysis-main-columns .analysis-column {
        display: flex;
        flex-direction: column;
    }

    .analysis-main-columns .analysis-column > .card {
        display: flex;
        flex-direction: column;
        width: 100%;
    }

    .analysis-main-columns .analysis-column > .accordion {
        width: 100%;
    }

    .analysis-right-bottom {
        margin-top: auto;
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

    /* Make main navigation buttons (< and >) twice as wide as << and >> */
    .board-nav-buttons {
        display: flex;
        gap: 0.5rem;
        justify-content: center;
        margin-top: 0.5rem;
    }
    .board-nav-buttons button {
        flex-grow: 1;
        flex-basis: 0;
    }
    #prev_move, #next_move {
        flex-grow: 2;
    }

    #playBoard .play-last-move {
        background-color: rgba(186, 202, 68, 0.55) !important;
    }

    .commentary-body {
        white-space: pre-wrap;
        line-height: 1.5;
    }

    .commentary-shell {
        display: grid;
        gap: 0.75rem;
    }

    .commentary-accordion,
    .commentary-accordion .accordion-item,
    .commentary-accordion .accordion-collapse,
    .commentary-accordion .accordion-body {
        width: 100%;
    }

    .commentary-accordion .accordion-item,
    .commentary-accordion .accordion-collapse,
    .commentary-accordion .accordion-body {
        display: flex;
        flex-direction: column;
        min-height: 0;
    }

    .commentary-accordion .accordion-item {
        max-height: var(--board-card-max-height);
    }

    .commentary-controls {
        display: flex;
        align-items: center;
        justify-content: flex-end;
        gap: 0.75rem;
        margin-bottom: 0.75rem;
    }

    .commentary-controls .btn {
        white-space: nowrap;
    }

    .commentary-accordion .accordion-button {
        font-weight: 600;
    }

    .commentary-scroll {
        flex: 1 1 auto;
        min-height: 0;
        overflow-y: auto;
        padding-right: 0.25rem;
    }

    .commentary-meta {
        font-size: 0.9rem;
    }

    @media (max-width: 991.98px) {
        .analysis-right-bottom {
            margin-top: 0;
        }

        .commentary-accordion,
        .commentary-accordion .accordion-item,
        .commentary-accordion .accordion-collapse,
        .commentary-accordion .accordion-body,
        .commentary-scroll {
            max-height: none;
        }
    }
"""

# JS utility for enabling/disabling elements visually and functionally
CUSTOM_JS = """
    const initPlayBoard = () => {
        const boardEl = document.getElementById("playBoard");
        if (!boardEl || !window.Chessboard) return;
        const clearLastMove = () => {
            boardEl
                .querySelectorAll(".play-last-move")
                .forEach((el) => el.classList.remove("play-last-move"));
        };
        const highlightLastMove = (from, to) => {
            clearLastMove();
            if (!from || !to) return;
            [from, to].forEach((square) => {
                const el =
                    boardEl.querySelector(`.square-${square}`) ||
                    boardEl.querySelector(`[data-square="${square}"]`);
                if (el) {
                    el.classList.add("play-last-move");
                }
            });
        };
        const board = Chessboard("playBoard", {
            draggable: true,
            pieceTheme:
                "https://raw.githubusercontent.com/oakmac/chessboardjs/master/website/img/chesspieces/wikipedia/{piece}.png",
            position: "start",
            onDrop: function(source, target) {
                Shiny.setInputValue("player_move", {from: source, to: target}, {priority: "event"});
                highlightLastMove(source, target);
                // Let the board move; server will correct invalid moves if needed.
                return undefined;
            }
        });

        Shiny.addCustomMessageHandler("board_update", function(message) {
            const payload = typeof message === "string" ? { fen: message } : message || {};
            if (!payload.fen) return;
            board.position(payload.fen, false);
            if (payload.last_move) {
                const from = payload.last_move.slice(0, 2);
                const to = payload.last_move.slice(2, 4);
                highlightLastMove(from, to);
            } else {
                clearLastMove();
            }
        });

        Shiny.addCustomMessageHandler("board_flip", function(message) {
            board.flip();
        });
    };

    document.addEventListener("DOMContentLoaded", initPlayBoard);
    document.addEventListener("shiny:connected", initPlayBoard);

    const initBoardCardSizing = () => {
        const boardCard = document.getElementById("analysis_board_card");
        if (!boardCard) return;

        const updateBoardCardHeight = () => {
            const height = boardCard.getBoundingClientRect().height;
            if (!height) return;
            document.documentElement.style.setProperty(
                "--board-card-max-height",
                `${height}px`
            );
        };

        if (!boardCard._resizeObserverAttached) {
            const observer = new ResizeObserver(() => updateBoardCardHeight());
            observer.observe(boardCard);
            boardCard._resizeObserverAttached = true;
        }

        requestAnimationFrame(updateBoardCardHeight);
    };

    document.addEventListener("DOMContentLoaded", initBoardCardSizing);
    document.addEventListener("shiny:connected", initBoardCardSizing);
    window.addEventListener("resize", initBoardCardSizing);

    const observeTable = (containerId, onChange) => {
        const container = document.getElementById(containerId);
        if (!container || container._observerAttached) return;
        const observer = new MutationObserver(onChange);
        observer.observe(container, { childList: true, subtree: true });
        container._observerAttached = true;
        onChange();
    };

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

    const scrollPlayMovesToBottom = () => {
        const container = document.getElementById("play_move_table_container");
        if (!container) return;
        const cells = container.querySelectorAll("td[data-ply]");
        const lastCell = cells[cells.length - 1];
        const maxPly = lastCell ? parseInt(lastCell.dataset.ply || "0", 10) : 0;
        const lastPly = parseInt(container.dataset.lastPly || "0", 10);
        if (maxPly === lastPly) return;
        container.dataset.lastPly = String(maxPly);
        requestAnimationFrame(() => {
            container.scrollTop = container.scrollHeight;
        });
    };

    document.addEventListener("click", (event) => {
        const cell = event.target.closest("td[data-ply]");
        if (!cell) return;

        const container = cell.closest("#move_table_container");
        if (!container) return;

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

    const initMoveObservers = () => {
        observeTable("move_table_container", scrollSelectedIntoView);
        observeTable("play_move_table_container", scrollPlayMovesToBottom);
    };

    document.addEventListener("DOMContentLoaded", initMoveObservers);
    document.addEventListener("shiny:connected", initMoveObservers);

    const initCommentaryAccordion = () => {
        const accordion = document.getElementById("commentary_accordion");
        if (!accordion || accordion._listenerAttached) return;
        const collapse = accordion.querySelector(".accordion-collapse");
        if (!collapse) return;

        const publish = () => {
            if (window.Shiny && Shiny.setInputValue) {
                Shiny.setInputValue(
                    "commentary_accordion_open",
                    collapse.classList.contains("show"),
                    { priority: "event" }
                );
            }
        };

        collapse.addEventListener("shown.bs.collapse", publish);
        collapse.addEventListener("hidden.bs.collapse", publish);
        accordion._listenerAttached = true;
        publish();
    };

    document.addEventListener("DOMContentLoaded", initCommentaryAccordion);
    document.addEventListener("shiny:connected", initCommentaryAccordion);

    document.addEventListener("keydown", (event) => {
        if (event.target.tagName === "INPUT" || event.target.tagName === "TEXTAREA") {
            return;
        }

        if (event.key === "ArrowLeft") {
            event.preventDefault();
            const prevButton = document.getElementById("prev_move");
            if (prevButton) {
                prevButton.click();
                prevButton.blur();
            }
        } else if (event.key === "ArrowRight") {
            event.preventDefault();
            const nextButton = document.getElementById("next_move");
            if (nextButton) {
                nextButton.click();
                nextButton.blur();
            }
        } else if (event.key === "ArrowUp") {
            event.preventDefault();
            if (window.Shiny && Shiny.setInputValue) {
                Shiny.setInputValue("move_back_2", Math.random(), { priority: "event" });
            }
        } else if (event.key === "ArrowDown") {
            event.preventDefault();
            if (window.Shiny && Shiny.setInputValue) {
                Shiny.setInputValue("move_forward_2", Math.random(), { priority: "event" });
            }
        }
    });

    Shiny.addCustomMessageHandler("clear_pgn_upload", function() {
        const upload = document.getElementById("pgn_upload");
        if (!upload || !upload.value) return;
        upload.value = "";
        upload.dispatchEvent(new Event("change", { bubbles: true }));
        const container = upload.closest(".shiny-input-container") || upload.parentElement;
        const label = container ? container.querySelector("label") : null;
        if (label) {
            label.textContent = "Upload PGN:";
        }
    });
"""

app_ui = ui.page_navbar(
    ui.nav_panel(
        "Analysis",
        ui.layout_sidebar(
            ui.sidebar(
                ui.input_file("pgn_upload", "Upload PGN:", accept=[".pgn", ".txt"]),
                ui.input_text_area(
                    "pgn_text",
                    "Or paste PGN:",
                    rows=8,
                ),
                ui.accordion(
                    ui.accordion_panel(
                        "Engine Settings",
                        ui.input_select(
                            "multipv",
                            "Engine lines",
                            choices=[str(value) for value in range(1, 9)],
                            selected="3",
                        ),
                        ui.input_select(
                            "think_time",
                            "Engine time (sec/move):",
                            choices=["0.3", "1", "3", "10"],
                            selected="1",
                        ),
                        ui.input_select(
                            "engine_threads",
                            "CPU threads:",
                            choices=[str(value) for value in range(1, 9)],
                            selected="8",
                        ),
                    ),
                    open=False,
                ),
                ui.input_select(
                    "evaluation_metric",
                    "Evaluation metric",
                    choices={
                        "cpl": "Centipawn loss (CPL)",
                        "wdl": "Expected score (WDL)",
                    },
                    selected="wdl",
                ),
                ui.input_action_button("annotate_moves", "Annotate Game"),
                ui.hr(),
                theme_picker_ui(),
            ),
            ui.layout_columns(
                ui.card(
                    ui.card_header("Game Info"),
                    ui.output_ui("game_info"),
                ),
                ui.layout_columns(
                    ui.div(
                        ui.card(
                            ui.card_header("Board"),
                            ui.div(ui.output_ui("board_view"), class_="board-frame"),
                            ui.div(
                                ui.input_action_button("first_move", "<<"),
                                ui.input_action_button("prev_move", "<"),
                                ui.input_action_button("next_move", ">"),
                                ui.input_action_button("last_move", ">>"),
                                class_="board-nav-buttons",
                            ),
                            ui.output_ui("fen_line"),
                            id="analysis_board_card",
                        ),
                        ui.card(
                            ui.output_text("eval_line"),
                            ui.output_ui("pv"),
                            ui.output_ui("prev_pv"),
                        ),
                        class_="analysis-column",
                    ),
                    ui.div(
                        ui.accordion(
                            ui.accordion_panel(
                                "LLM Commentary",
                                ui.div(
                                    ui.output_ui("commentary_panel"),
                                    class_="commentary-scroll",
                                ),
                                value="commentary",
                            ),
                            id="commentary_accordion",
                            open=False,
                            multiple=False,
                            class_="commentary-accordion mb-3",
                        ),
                        ui.div(
                            ui.card(
                                ui.card_header("Moves"),
                                ui.div(
                                    ui.output_ui("move_list"),
                                    id="move_table_container",
                                    class_="move-table-wrap",
                                ),
                            ),
                            ui.card(
                                ui.card_header("Evaluation Graph"),
                                output_widget("eval_graph"),
                            ),
                            ui.card(
                                ui.card_header("Move Summary"),
                                ui.output_ui("move_summary"),
                            ),
                            class_="analysis-right-bottom",
                        ),
                        class_="analysis-column",
                    ),
                    col_widths=[7, 5],
                    class_="analysis-main-columns",
                ),
                col_widths=[12, 12],
            ),
        ),
    ),
    ui.nav_panel(
        "Play",
        ui.layout_sidebar(
            ui.sidebar(
                ui.input_action_button("flipPlayBoard", "Flip Board"),
                ui.input_action_button("analyze_play_position", "Analyze Position"),
                ui.input_action_button("resetPlayBoard", "Reset Board"),
                ui.input_slider(
                    "enginePlayElo",
                    "Engine Elo",
                    min=1400,
                    max=3000,
                    value=1600,
                    step=100,
                ),
                ui.input_select(
                    "engine_side",
                    "Engine plays",
                    choices={
                        "none": "None",
                        "black": "Black",
                        "white": "White",
                    },
                    selected="black",
                ),
            ),
            ui.layout_columns(
                ui.card(
                    ui.div(
                        ui.div(id="playBoard", style="width: 720px"),
                        class_="d-flex justify-content-center",
                    ),
                ),
                ui.card(
                    ui.card_header("Moves"),
                    ui.div(
                        ui.output_ui("play_move_list"),
                        id="play_move_table_container",
                        class_="move-table-wrap",
                    ),
                    ui.div(
                        ui.download_button("download_play_pgn", "Download PGN"),
                        class_="d-flex justify-content-center mt-2",
                    ),
                ),
                col_widths=[8, 4],
            ),
        ),
    ),
    ui.nav_panel(
        "Library",
        ui.layout_sidebar(
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
    theme=shinyswatch.theme.flatly,
    fillable=True,
    header=[
        ui.tags.style(CUSTOM_CSS),
        ui.tags.link(
            rel="stylesheet",
            href="https://unpkg.com/@chrisoakman/chessboardjs@1.0.0/dist/chessboard-1.0.0.min.css",
        ),
        ui.tags.script(
            src="https://unpkg.com/@chrisoakman/chessboardjs@1.0.0/dist/chessboard-1.0.0.min.js"
        ),
        ui.tags.script(CUSTOM_JS),
    ],
    id="main_nav",
)
