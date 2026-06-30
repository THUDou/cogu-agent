
export function mul(matrix1 = [1, 0, 0, 1], matrix2 = [1, 0, 0, 1]) {
    if (matrix1.length === 4) {
        return [
            matrix1[0] * matrix2[0] + matrix1[2] * matrix2[1],
            matrix1[1] * matrix2[0] + matrix1[3] * matrix2[1],
            matrix1[0] * matrix2[2] + matrix1[2] * matrix2[3],
            matrix1[1] * matrix2[2] + matrix1[3] * matrix2[3]
        ];
    }

    return [
        matrix1[0] * matrix2[0] + matrix1[2] * matrix2[1],
        matrix1[1] * matrix2[0] + matrix1[3] * matrix2[1],
        matrix1[0] * matrix2[2] + matrix1[2] * matrix2[3],
        matrix1[1] * matrix2[2] + matrix1[3] * matrix2[3],

        matrix1[0] * matrix2[4] + matrix1[2] * matrix2[5] + matrix1[4],
        matrix1[1] * matrix2[4] + matrix1[3] * matrix2[5] + matrix1[5]
    ];
}

export function multiply(...matrixs) {
    let result = matrixs[0];
    for (let i = 1, matrix; (matrix = matrixs[i]); i++) {
        result = mul(result, matrix);
    }

    return result;
}
