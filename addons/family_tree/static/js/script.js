import diffArrays, { updatedValues } from '/static/family_tree/js/diff-arrays.js';

let lastTreeState = null;
var f3Chart = null;

const initialData = [{
    "id": crypto.randomUUID(),
    "data": {
        "name": "Root Node",
    },
    "rels": {}
}];

var deepCopy = (obj) => JSON.parse(JSON.stringify(obj));

function storeData(tree) {
    const newData = tree.getStoreData()

    const changes = diffArrays(lastTreeState, newData, 'id', {
        updatedValues: updatedValues.both
    });

    if (changes.updated.length) {
        fetch("/api/v2/family-tree/update", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(changes.updated),
        }).then(res => res.json())
            .then((res) => {
                console.log("Cambios guardados exitosamente");
            })
            .catch(error => {
                console.error("Error guardando:", error);
            });
    }
    if (changes.removed.length) {
        fetch("/api/v2/family-tree/remove", {
            method: "DELETE",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(changes.removed),
        }).then(res => res.json())
            .then((res) => {
                console.log("Cambios guardados exitosamente");
            })
            .catch(error => {
                console.error("Error guardando:", error);
            });
    }
    if (changes.added.length) {
        fetch("/api/v2/family-tree/add", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(changes.added),
        }).then(res => res.json())
            .then((res) => {
                console.log("Cambios guardados exitosamente");
            })
            .catch(error => {
                console.error("Error guardando:", error);
            });
    }
    lastTreeState = deepCopy(newData); // Actualizar estado anterior
}

// Carga inicial
fetch("/api/v2/family-tree/")
    .then((response) => response.json())
    .then((serverData) => {
        // Inicializar con datos del servidor o datos iniciales
        const initialChartData = serverData.length > 0 ? serverData : initialData;

        f3Chart = f3.createChart('#FamilyChart', initialChartData);
        lastTreeState = deepCopy(initialChartData);

        // Configuración del chart
        f3Chart.setTransitionTime(1000)
            .setCardXSpacing(160)
            .setCardYSpacing(150)
            .setOrientationVertical()
            .setSingleParentEmptyCard(true, { label: 'ADD' });

        const f3Card = f3Chart.setCard(f3.CardHtml)
            .setCardDisplay([["name"], []])
            .setMiniTree(true)
            .setStyle('imageCircle')
            .setOnHoverPathToMain();

        const f3EditTree = f3Chart.editTree()
            .setFields(["name", "avatar", {}]);

        f3Card.setOnCardClick((e, d) => {
            f3EditTree.open(d);
            if (!f3EditTree.isAddingRelative()) {
                f3Chart.store.updateMainId(d.data.id);
                f3Card.onCardClickDefault(e, d);
            }
        });

        f3Chart.updateTree({ initial: true });
        f3EditTree.open(f3Chart.getMainDatum());
        f3EditTree.setOnChange(() => storeData(f3EditTree));
    })
    .catch(error => {
        console.error("Error cargando datos:", error);
        f3Chart = f3.createChart('#FamilyChart', initialData);
        lastTreeState = deepCopy(initialChartData);
    });