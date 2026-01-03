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
        --play-board-size: 420px;
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
    #prev_move, #next_move, #play_prev_move, #play_next_move {
        flex-grow: 2;
    }

    .play-board {
        width: var(--play-board-size);
        max-width: 100%;
        margin: 0 auto;
    }

    .play-board .board-b72b1 {
        border-radius: 0.25rem;
    }

    .png-editor {
        display: grid;
        gap: 0.75rem;
    }

    .png-canvas {
        width: 100%;
        height: auto;
        border: 1px solid var(--bs-border-color, #dee2e6);
        border-radius: 0.25rem;
        background: #ffffff;
        cursor: crosshair;
    }
"""

# JS utility for enabling/disabling elements visually and functionally
CUSTOM_JS = """
    const scrollSelectedIntoView = (container) => {
        if (!container) return;
        const selected = container.querySelector("td.is-selected");
        if (!selected) return;
        const selectedRect = selected.getBoundingClientRect();
        const containerRect = container.getBoundingClientRect();
        if (selectedRect.top < containerRect.top || selectedRect.bottom > containerRect.bottom) {
            selected.scrollIntoView({ block: "nearest" });
        }
    };

    const observeMoveTable = (containerId) => {
        const container = document.getElementById(containerId);
        if (!container || container._observerAttached) return;
        const observer = new MutationObserver(() => scrollSelectedIntoView(container));
        observer.observe(container, { childList: true, subtree: true });
        container._observerAttached = true;
    };

    const observeMoveTables = () => {
        observeMoveTable("move_table_container");
        observeMoveTable("play_move_table_container");
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

        const playContainer = cell.closest("#play_move_table_container");
        const analysisContainer = cell.closest("#move_table_container");
        const isPlayTable = Boolean(playContainer);
        const inputName = isPlayTable ? "play_move_cell" : "move_cell";
        if (window.Shiny && Shiny.setInputValue) {
            Shiny.setInputValue(inputName, { ply: ply }, { priority: "event" });
        }

        scrollSelectedIntoView(playContainer || analysisContainer);
    });

    document.addEventListener("DOMContentLoaded", observeMoveTables);
    document.addEventListener("shiny:connected", observeMoveTables);

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

    const initPlayBoard = () => {
        const boardEl = document.getElementById("play_board");
        if (!boardEl || boardEl._board || typeof Chessboard === "undefined") return;

        const onDrop = (source, target, piece) => {
            if (!window.Shiny || !Shiny.setInputValue) return;
            if (source === target) return;
            let promotion = "";
            if (piece && piece.endsWith("P")) {
                const targetRank = parseInt(target[1], 10);
                if (targetRank === 1 || targetRank === 8) {
                    promotion = "q";
                }
            }
            Shiny.setInputValue(
                "play_move",
                { from: source, to: target, promotion: promotion },
                { priority: "event" }
            );
        };

        const config = {
            draggable: true,
            position: "start",
            onDrop: onDrop,
        };

        boardEl._board = Chessboard("play_board", config);
    };

    const initPlayPngEditor = () => {
        const canvas = document.getElementById("play_png_canvas");
        if (!canvas || canvas._initialized) return;
        const ctx = canvas.getContext("2d");
        ctx.fillStyle = "#ffffff";
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.lineWidth = 2;
        ctx.lineCap = "round";
        ctx.strokeStyle = "#1f2328";

        let drawing = false;
        const getPos = (event) => {
            const rect = canvas.getBoundingClientRect();
            const scaleX = canvas.width / rect.width;
            const scaleY = canvas.height / rect.height;
            return {
                x: (event.clientX - rect.left) * scaleX,
                y: (event.clientY - rect.top) * scaleY,
            };
        };

        const startDraw = (event) => {
            drawing = true;
            const { x, y } = getPos(event);
            ctx.beginPath();
            ctx.moveTo(x, y);
        };
        const draw = (event) => {
            if (!drawing) return;
            const { x, y } = getPos(event);
            ctx.lineTo(x, y);
            ctx.stroke();
        };
        const endDraw = () => {
            drawing = false;
            ctx.closePath();
        };

        canvas.addEventListener("mousedown", startDraw);
        canvas.addEventListener("mousemove", draw);
        canvas.addEventListener("mouseup", endDraw);
        canvas.addEventListener("mouseleave", endDraw);

        const upload = document.getElementById("play_png_upload");
        if (upload) {
            upload.addEventListener("change", (event) => {
                const file = event.target.files[0];
                if (!file) return;
                const reader = new FileReader();
                reader.onload = () => {
                    const img = new Image();
                    img.onload = () => {
                        ctx.clearRect(0, 0, canvas.width, canvas.height);
                        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
                    };
                    img.src = reader.result;
                };
                reader.readAsDataURL(file);
            });
        }

        const clearButton = document.getElementById("play_png_clear");
        if (clearButton) {
            clearButton.addEventListener("click", () => {
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                ctx.fillStyle = "#ffffff";
                ctx.fillRect(0, 0, canvas.width, canvas.height);
            });
        }

        const downloadButton = document.getElementById("play_png_download");
        if (downloadButton) {
            downloadButton.addEventListener("click", () => {
                const link = document.createElement("a");
                link.href = canvas.toDataURL("image/png");
                link.download = "board.png";
                link.click();
            });
        }

        canvas._initialized = true;
    };

    const initPlayBoardHandlers = () => {
        initPlayBoard();
        initPlayPngEditor();
    };

    document.addEventListener("DOMContentLoaded", initPlayBoardHandlers);
    document.addEventListener("shiny:connected", initPlayBoardHandlers);

    if (window.Shiny) {
        Shiny.addCustomMessageHandler("play_set_fen", (payload) => {
            const boardEl = document.getElementById("play_board");
            if (!boardEl || !boardEl._board) return;
            if (payload && payload.fen) {
                boardEl._board.position(payload.fen, false);
            }
        });

        Shiny.addCustomMessageHandler("play_set_orientation", (payload) => {
            const boardEl = document.getElementById("play_board");
            if (!boardEl || !boardEl._board) return;
            if (payload && payload.orientation) {
                boardEl._board.orientation(payload.orientation);
            }
        });
    }
"""

app_ui = ui.page_navbar(
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
                    "annotation_metric",
                    "Annotation metric",
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
                    ),
                    ui.card(
                        ui.output_text("eval_line"),
                        ui.output_ui("pv"),
                        ui.output_ui("prev_pv"),
                    ),
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
                        ui.card_header("Move Summary"),
                        ui.output_ui("move_summary"),
                    ),
                    ui.card(
                        ui.card_header("Evaluation Graph"),
                        output_widget("eval_graph"),
                    ),
                ),
                col_widths=[12, 7, 5],
            ),
        ),
    ),
    ui.nav_panel(
        "Play",
        ui.page_sidebar(
            ui.sidebar(
                ui.input_select(
                    "play_opponent",
                    "Opponent",
                    choices={"engine": "Stockfish", "self": "Self"},
                    selected="engine",
                ),
                ui.input_slider(
                    "play_skill",
                    "Engine strength",
                    min=0,
                    max=20,
                    value=10,
                ),
                ui.input_switch("play_rotate", "Rotate board", value=False),
                ui.input_switch("play_eval", "Show evaluation", value=True),
                ui.input_action_button("play_reset", "Reset game"),
            ),
            ui.layout_columns(
                ui.div(
                    ui.card(
                        ui.card_header("Board"),
                        ui.div(ui.tags.div(id="play_board"), class_="play-board"),
                        ui.div(
                            ui.input_action_button("play_first_move", "<<"),
                            ui.input_action_button("play_prev_move", "<"),
                            ui.input_action_button("play_next_move", ">"),
                            ui.input_action_button("play_last_move", ">>"),
                            class_="board-nav-buttons",
                        ),
                        ui.output_text("play_status"),
                        ui.output_text("play_eval"),
                    ),
                    ui.card(
                        ui.card_header("Moves"),
                        ui.div(
                            ui.output_ui("play_move_list"),
                            id="play_move_table_container",
                            class_="move-table-wrap",
                        ),
                    ),
                ),
                ui.card(
                    ui.card_header("Editable PNG"),
                    ui.div(
                        ui.input_file(
                            "play_png_upload",
                            "Load PNG",
                            accept=[".png"],
                        ),
                        ui.tags.canvas(
                            id="play_png_canvas",
                            width="480",
                            height="480",
                            class_="png-canvas",
                        ),
                        ui.div(
                            ui.input_action_button("play_png_clear", "Clear"),
                            ui.input_action_button("play_png_download", "Download PNG"),
                            class_="d-flex gap-2",
                        ),
                        class_="png-editor",
                    ),
                ),
                col_widths=[7, 5],
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
    theme=shinyswatch.theme.flatly,
    fillable=True,
    header=[
        ui.tags.link(
            rel="stylesheet",
            href="https://cdnjs.cloudflare.com/ajax/libs/chessboard-js/1.0.0/chessboard-1.0.0.min.css",
        ),
        ui.tags.script(src="https://cdnjs.cloudflare.com/ajax/libs/jquery/3.6.4/jquery.min.js"),
        ui.tags.script(
            src="https://cdnjs.cloudflare.com/ajax/libs/jqueryui/1.13.2/jquery-ui.min.js"
        ),
        ui.tags.script(
            src="https://cdnjs.cloudflare.com/ajax/libs/chessboard-js/1.0.0/chessboard-1.0.0.min.js"
        ),
        ui.tags.style(CUSTOM_CSS),
        ui.tags.script(CUSTOM_JS),
    ],
)
