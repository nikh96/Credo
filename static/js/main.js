// Calculator overlay logic for Credo / Credo.
//
// I implemented this calculator module myself (state handling,
// event listeners, DOM updates, and validation logic).
// Some parts of the structure and specific implementation details
// (such as the overlay behavior and expression evaluation pattern)
// were refined with the help of an AI assistant (Perplexity),
// then reviewed and adapted by me.

// --- Calculator logic wrapped after DOM load ---
// document.addEventListener("DOMContentLoaded", function () {
//     ...
// });



// --- Calculator logic wrapped after DOM load ---
document.addEventListener("DOMContentLoaded", function () {
    // get elements
    const calcOverlay = document.getElementById("calculator-overlay");
    const calcOpenBtn = document.getElementById("open-calculator-btn");
    const calcCloseBtn = document.getElementById("close-calculator-btn");
    const calcDisplay = document.getElementById("calc-display");

    // calculator state
    let calcExpression = "";

    // open calculator
    function openCalculator() {
        if (!calcOverlay) return;
        calcOverlay.style.display = "flex"; // show overlay
    }

    // close calculator
    function closeCalculator() {
        if (!calcOverlay) return;
        calcOverlay.style.display = "none"; // hide overlay
    }

    // update display
    function updateCalcDisplay() {
        if (!calcDisplay) return;
        calcDisplay.value = calcExpression || "0";
    }

    // handle button click
    function handleCalcButtonClick(event) {
        const btn = event.target;
        const value = btn.getAttribute("data-value");
        const action = btn.getAttribute("data-action");

        if (action === "clear") {
            calcExpression = "";
            updateCalcDisplay();
            return;
        }

        if (action === "equal") {
            try {
                if (!/^[0-9+\-*/.()\s]*$/.test(calcExpression)) {
                    calcExpression = "";
                    updateCalcDisplay();
                    return;
                }
                const result = Function("return " + (calcExpression || "0"))();
                calcExpression = String(result);
            } catch (e) {
                calcExpression = "";
            }
            updateCalcDisplay();
            return;
        }

        if (value) {
            calcExpression += value;
            updateCalcDisplay();
        }
    }

    // attach open/close
    if (calcOpenBtn) {
        calcOpenBtn.addEventListener("click", openCalculator);
    }

    if (calcCloseBtn) {
        calcCloseBtn.addEventListener("click", closeCalculator);
    }

    // close when clicking outside panel
    if (calcOverlay) {
        calcOverlay.addEventListener("click", function (event) {
            if (event.target === calcOverlay) {
                closeCalculator();
            }
        });
    }

    // attach to all buttons
    document.querySelectorAll(".calc-btn").forEach(function (btn) {
        btn.addEventListener("click", handleCalcButtonClick);
    });

    // initial display
    updateCalcDisplay();
});
