import deepDiff from '/family_tree/libs/deep-diff.mjs';

const updatedValues = {
    simple: 1,
    detailed: 2
};

const diffArrays = (first = [], second = [], idField = 'id', options = {}) => {
    const opts = {
        compareFunction: _.isEqual,
        outputFormat: updatedValues.simple,
        ...options,
    };

    // Validaciones
    if (!_.isArray(first)) throw new Error('"first" debe ser un array');
    if (!_.isArray(second)) throw new Error('"second" debe ser un array');
    if (!_.isString(idField)) throw new Error('"idField" debe ser string');
    if (!_.isObject(options)) throw new Error('"options" debe ser objeto');
    if (![updatedValues.simple, updatedValues.detailed].includes(opts.outputFormat)) {
        throw new Error('Formato de salida no válido');
    }

    const firstIds = [];
    const secondIds = [];

    // Indexar primer array
    const firstIndex = _.keyBy(first, (item) => {
        firstIds.push(item[idField]);
        return item[idField];
    });

    // Función de agrupación
    const groupingFunction = (item) => {
        const itemId = item[idField];
        secondIds.push(itemId);

        const oldItem = firstIndex[itemId];

        if (!oldItem) return 'added';
        return opts.compareFunction(oldItem, item) ? 'same' : 'updated';
    };

    // Agrupar elementos
    const result = _.groupBy(second, groupingFunction);

    // Procesar actualizados según formato
    if (result.updated) {
        result.updated = result.updated.map(item => {
            const oldVersion = firstIndex[item[idField]];

            return opts.outputFormat === updatedValues.detailed
                ? { old: oldVersion, new: item }
                : item;
        });
    }

    // Procesar eliminados (solo IDs)
    const removedIds = _.difference(firstIds, secondIds);

    return {
        added: result.added || [],
        updated: result.updated || [],
        removed: removedIds,
        same: result.same || []
    };
};

export { updatedValues };
export default diffArrays;