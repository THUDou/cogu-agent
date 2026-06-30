
import cffStandardStrings from './cffStandardStrings';

export default function getCFFString(strings, index) {
    if (index <= 390) {
        index = cffStandardStrings[index];
    }
    else {
        index = strings[index - 391];
    }

    return index;
}
