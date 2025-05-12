import diffArrays, { updatedValues } from '/family_tree/libs/diff-arrays.js';

let lastTreeState = null;
var f3Chart = null;

function uuidv4() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
        const r = Math.random() * 16 | 0,
            v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

const initialData = [{
    "id": uuidv4(),
    "data": {
        "name": "Root Node",
    },
    "rels": {}
}];

function loadFieldsFromServer() {
    const defaultFields = [
        { id: "name", type: "text", label: "The Name", required: true },
        { id: "avatar", type: "image", label: "Avatar", required: true },
        { id: "birth_date", type: "text", label: "Birth Date", required: true }
    ];

    return fetch("/api/v2/family-tree/schema")
        .then((response) => {
            if (!response.ok) {
                throw new Error("No se pudo cargar el schema");
            }
            return response.json();
        }).then((data) => {
            return data.filter(field => field.id !== "gender");
        })
        .catch((error) => {
            console.warn("Error al cargar schema del servidor, usando campos por defecto:", error);
            return defaultFields;
        });
}

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

fetch("/api/v2/family-tree/")
    .then((response) => response.json())
    .then((serverData) => {
        const initialChartData = serverData.length > 0 ? serverData : initialData;

        f3Chart = f3.createChart('#FamilyChart', initialChartData);
        lastTreeState = deepCopy(initialChartData);

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

        // Aquí esperamos a que se carguen los campos del servidor
        loadFieldsFromServer().then((fieldData) => {
            const f3EditTree = f3Chart.editTree().setFields(fieldData);

            f3Card.setOnCardClick((e, d) => {
                f3EditTree.open(d);
                if (!f3EditTree.isAddingRelative()) {
                    f3Chart.store.updateMainId(d.data.id);
                    f3Card.onCardClickDefault(e, d);
                    localStorage.setItem("mainId", d.data.id);
                }
            });

            const savedMainId = localStorage.getItem("mainId");
            if (savedMainId) {
                f3Chart.store.updateMainId(savedMainId);
            }

            f3Chart.updateTree({ initial: true });
            f3EditTree.open(f3Chart.getMainDatum());
            f3EditTree.setOnChange(() => storeData(f3EditTree));
        });
    })
    .catch((error) => {
        console.error("Error cargando datos:", error);
        f3Chart = f3.createChart('#FamilyChart', initialData);
        lastTreeState = deepCopy(initialData);
    });