document.addEventListener("DOMContentLoaded", () => {
    let draggedCard = null;
    let sourceContainer = null;

    const cards = document.querySelectorAll(".opportunity-card");
    const containers = document.querySelectorAll(
        ".pipeline-column__cards"
    );

    function getCookie(name) {
        const cookieValue = document.cookie
            .split("; ")
            .find((row) => row.startsWith(`${name}=`));

        return cookieValue
            ? decodeURIComponent(cookieValue.split("=")[1])
            : "";
    }

    function updateColumnCounts() {
        containers.forEach((container) => {
            const count = container.querySelectorAll(
                ".opportunity-card"
            ).length;

            const column = container.closest(".pipeline-column");
            const countLabel = column.querySelector(
                ".pipeline-column__eyebrow"
            );

            countLabel.textContent = `${count} fırsat`;
        });
    }

    cards.forEach((card) => {
        card.addEventListener("dragstart", (event) => {
            draggedCard = card;
            sourceContainer = card.parentElement;

            card.classList.add("is-dragging");
            event.dataTransfer.effectAllowed = "move";
        });

        card.addEventListener("dragend", () => {
            card.classList.remove("is-dragging");

            containers.forEach((container) => {
                container.classList.remove("is-drop-target");
            });
        });
    });

    containers.forEach((container) => {
        container.addEventListener("dragover", (event) => {
            event.preventDefault();

            if (draggedCard && container !== sourceContainer) {
                container.classList.add("is-drop-target");
            }
        });

        container.addEventListener("dragleave", () => {
            container.classList.remove("is-drop-target");
        });

        container.addEventListener("drop", async (event) => {
            event.preventDefault();
            container.classList.remove("is-drop-target");

            if (!draggedCard || container === sourceContainer) {
                return;
            }

            const opportunityId = draggedCard.dataset.opportunityId;
            const targetStage = container.dataset.stage;

            container.appendChild(draggedCard);
            updateColumnCounts();

            try {
                const response = await fetch(
                    `/crm/opportunities/${opportunityId}/stage/`,
                    {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json",
                            "X-CSRFToken": getCookie("csrftoken"),
                        },
                        body: JSON.stringify({
                            stage: targetStage,
                        }),
                    }
                );

                if (!response.ok) {
                    throw new Error("Fırsat aşaması güncellenemedi.");
                }
            } catch (error) {
                sourceContainer.appendChild(draggedCard);
                updateColumnCounts();

                window.alert(
                    "Aşama güncellenemedi. Lütfen tekrar deneyin."
                );
            }
        });
    });
});