
export namespace TTF {
  type CodePoint = number;

  type Point = {
    x: number;
    y: number;
    onCurve: boolean;
  };

  type Contour = Point[];

  type Glyph = {
    contours: Contour[];
    xMin: number;
    yMin: number;
    xMax: number;
    yMax: number;
    advanceWidth: number;
    leftSideBearing: number;
    name: string;
    unicode: CodePoint[];
  };

  type Head = {
    [k: string]: number;
    version: number;
    fontRevision: number;
    checkSumAdjustment: number;
    magickNumber: number;
    flags: number;
    unitsPerE: number;
    created: number;
    modified: number;
    xMin: number;
    yMin: number;
    xMax: number;
    yMax: number;
    macStyle: number;
    lowestRecPPEM: number;
    fontDirectionHint: number;
    indexToLocFormat: number;
    glyphDataFormat: number;
  };

  type Hhea = {
    version: number;
    ascent: number;
    descent: number;
    lineGap: number;
    advanceWidthMax: number;
    minLeftSideBearing: number;
    minRightSideBearing: number;
    xMaxExtent: number;
    caretSlopeRise: number;
    caretSlopeRun: number;
    caretOffset: number;
    reserved0: number;
    reserved1: number;
    reserved2: number;
    reserved3: number;
    metricDataFormat: number;
    numOfLongHorMetrics: number;
  };

  type Post = {
    italicAngle: number;
    postoints: number;
    underlinePosition: number;
    underlineThickness: number;
    isFixedPitch: number;
    minMemType42: number;
    maxMemType42: number;
    minMemType1: number;
    maxMemType1: number;
    format: number;
  };

  type Maxp = {
    version: number;
    numGlyphs: number;
    maxPoints: number;
    maxContours: number;
    maxCompositePoints: number;
    maxCompositeContours: number;
    maxZones: number;
    maxTwilightPoints: number;
    maxStorage: number;
    maxFunctionDefs: number;
    maxStackElements: number;
    maxSizeOfInstructions: number;
    maxComponentElements: number;
    maxComponentDepth: number;
  };

  type OS2 = {
    version: number;
    xAvgCharWidth: number;
    usWeightClass: number;
    usWidthClass: number;
    fsType: number;
    ySubscriptXSize: number;
    ySubscriptYSize: number;
    ySubscriptXOffset: number;
    ySubscriptYOffset: number;
    ySuperscriptXSize: number;
    ySuperscriptYSize: number;
    ySuperscriptXOffset: number;
    ySuperscriptYOffset: number;
    yStrikeoutSize: number;
    yStrikeoutPosition: number;
    sFamilyClass: number;
    bFamilyType: number;
    bSerifStyle: number;
    bWeight: number;
    bProportion: number;
    bContrast: number;
    bStrokeVariation: number;
    bArmStyle: number;
    bLetterform: number;
    bMidline: number;
    bXHeight: number;
    ulUnicodeRange1: number;
    ulUnicodeRange2: number;
    ulUnicodeRange3: number;
    ulUnicodeRange4: number;
    achVendID: string;
    fsSelection: number;
    usFirstCharIndex: number;
    usLastCharIndex: number;
    sTypoAscender: number;
    sTypoDescender: number;
    sTypoLineGap: number;
    usWinAscent: number;
    usWinDescent: number;
    ulCodePageRange1: number;
    ulCodePageRange2: number;
    sxHeight: number;
    sCapHeight: number;
    usDefaultChar: number;
    usBreakChar: number;
    usMaxContext: number;
  };

  type Name = {
    [k: string]: string;
    fontFamily: string;
    fontSubFamily: string;
    uniqueSubFamily: string;
    version: string;
  };

  type Metrics = {
    ascent: number;
    descent: number;
    sTypoAscender: number;
    sTypoDescender: number;
    usWinAscent: number;
    usWinDescent: number;
    sxHeight: number;
    sCapHeight: number;
  }


  type TTFObject = {
    version: number;
    numTables: number;
    searchRange: number;
    entrySelector: number;
    rangeShift: number;
    head: Head;
    glyf: Glyph[];
    cmap: Record<string, number>;
    name: Name;
    hhea: Hhea;
    post: Post;
    maxp: Maxp;
    "OS/2": OS2;
  };
}

export namespace FontEditor {
  type FontType = "ttf" | "otf" | "eot" | "woff" | "woff2" | "svg";

  type FontInput = ArrayBuffer | Buffer | string | Document;
  type FontOutput = ArrayBuffer | Buffer | string;

  type UInt8 = number;

  interface FontReadOptions {
    type: FontType;

    subset?: TTF.CodePoint[];

    hinting?: boolean;

    kerning?: boolean;

    compound2simple?: boolean;

    inflate?: (deflatedData: UInt8[]) => UInt8[];

    combinePath?: boolean;
  }

  interface FontWriteOptions {
    type: FontType;

    toBuffer?: boolean;

    hinting?: boolean;

    kerning?: boolean,

    writeZeroContoursGlyfData?: boolean;

    metadata?: string;

    deflate?: (rawData: UInt8[]) => UInt8[];

    support?: {
      head?: {
        xMin?: number;
        yMin?: number;
        xMax?: number;
        yMax?: number;
      };
      hhea?: {
        advanceWidthMax?: number;
        xMaxExtent?: number;
        minLeftSideBearing?: number;
        minRightSideBearing?: number;
      };
    };
  }

  type FindCondition = {
    unicode?: TTF.CodePoint[];
    name?: string;
    filter?: (glyph: TTF.Glyph) => boolean;
  };

  type MergeOptions =
    | {
        scale: number;
      }
    | {
        adjustGlyf: boolean;
      };

  type OptimizeResult = {
    result:
      | true
      | {
          repeat: number[];
        };
  };

  class TTFHelper {
    constructor(ttf: TTF.TTFObject);

    codes(): string[];

    getGlyfIndexByCode(c: string | number): number | undefined;

    getGlyfByIndex(glyfIndex: number): TTF.Glyph | undefined;

    getGlyfByCode(c: string | number): TTF.Glyph | undefined;

    set(ttf: TTF.TTFObject): this;

    get(): TTF.TTFObject;

    addGlyf(glyf: TTF.Glyph): [TTF.Glyph];

    insertGlyf(glyf: TTF.Glyph, insertIndex?: number): [TTF.Glyph];

    mergeGlyf(imported: TTF.TTFObject, options?: MergeOptions): TTF.Glyph[];

    removeGlyf(indexList: number[]): TTF.Glyph[];

    setUnicode(unicode: string, indexList?: number[], isGenerateName?: boolean): TTF.Glyph[];

    genGlyfName(indexList?: number[]): TTF.Glyph[];

    clearGlyfName(indexList?: number[]): TTF.Glyph[];

    appendGlyf(glyfList: TTF.Glyph[], indexList?: number[]): TTF.Glyph[];

    adjustGlyfPos(indexList: number[] | undefined, setting: {
      leftSideBearing?: number;
      rightSideBearing?:number;
      verticalAlign?: number
    }): TTF.Glyph[];

    adjustGlyf(indexList: number[] | undefined, setting: {
        reverse?: boolean,
        mirror?: boolean,
        scale?: number,
        adjustToEmBox?: boolean,
        adjustToEmPadding?: number,
    }): TTF.Glyph[];

    getGlyf(indexList?: number[]): TTF.Glyph[];

    findGlyf(condition: FindCondition): number[];

    replaceGlyf(glyf: TTF.Glyph, index: number): [TTF.Glyph];

    setGlyf(glyfList: TTF.Glyph[]): TTF.Glyph[];

    sortGlyf(): TTF.Glyph[] | -1 | -2;

    setName(name: Partial<TTF.Name>): TTF.Name;

    setHead(head: Partial<TTF.Head>): TTF.Head;

    setHhea(fields: Partial<TTF.Hhea>): TTF.Hhea;

    setOS2(fields: Partial<TTF.OS2>): TTF.OS2;

    setPost(fields: Partial<TTF.Post>): TTF.Post;

    calcMetrics(): TTF.Metrics;

    optimize(): OptimizeResult;

    compound2simple(indexList?: number[]): TTF.Glyph[];
  }

  interface TTFReaderOptions {
    subset?: number[];      // Font subset array, defaults to []
    hinting?: boolean;      // Whether to preserve hinting information, defaults to false
    kerning?: boolean;      // Whether to preserve kerning information, defaults to false
    compound2simple?: boolean;  // Whether to convert compound glyphs to simple glyphs, defaults to false
  }

  class TTFReader {
    constructor(options?: TTFReaderOptions);
    protected readBuffer(buffer: ArrayBuffer): TTF.TTFObject;
    protected resolveGlyf(ttf: TTF.TTFObject): void;
    protected cleanTables(ttf: TTF.TTFObject): void;

    read(buffer: ArrayBuffer): TTF.TTFObject;

    dispose(): void;
  }


  interface TTFWriterOptions {
    writeZeroContoursGlyfData?: boolean;
    hinting?: boolean;
    kerning?: boolean;
    support?: Record<string, any>;
  }

  class TTFWriter {
    constructor(options?: TTFWriterOptions);
    protected resolveTTF(ttf: TTF.TTFObject): void;
    protected dump(ttf: TTF.TTFObject): ArrayBuffer;
    protected prepareDump(ttf: TTF.TTFObject): void;
    write(ttf: TTF.TTFObject): ArrayBuffer;
    dispose(): void;
  }


  class Reader {
    private offset: number;

    private length: number;

    private littleEndian: boolean;

    private view: DataView;

    constructor(buffer: ArrayBuffer | ArrayLike<number>, offset?: number, length?: number, littleEndian?: boolean);

    read(type: string, offset?: number, littleEndian?: boolean): number;

    readBytes(offset: number, length?: number): number[];

    readString(offset: number, length?: number): string;

    readChar(offset: number): string;

    readUint24(offset?: number): number;

    readFixed(offset?: number): number;

    readLongDateTime(offset?: number): Date;

    seek(offset?: number): this;

    dispose(): void;

    readInt8(offset?: number, littleEndian?: boolean): number;
    readInt16(offset?: number, littleEndian?: boolean): number;
    readInt32(offset?: number, littleEndian?: boolean): number;
    readUint8(offset?: number, littleEndian?: boolean): number;
    readUint16(offset?: number, littleEndian?: boolean): number;
    readUint32(offset?: number, littleEndian?: boolean): number;
    readFloat32(offset?: number, littleEndian?: boolean): number;
    readFloat64(offset?: number, littleEndian?: boolean): number;
  }

  class Writer {
    private offset: number;
    private length: number;
    private littleEndian: boolean;
    private view: DataView;
    private _offset: number;

    constructor(buffer: ArrayBuffer, offset?: number, length?: number, littleEndian?: boolean);

    write(type: string, value: number, offset?: number, littleEndian?: boolean): this;

    writeBytes(value: ArrayBuffer | number[], length?: number, offset?: number): this;

    writeEmpty(length: number, offset?: number): this;

    writeString(str?: string, length?: number, offset?: number): this;

    writeChar(value: string, offset?: number): this;

    writeFixed(value: number, offset?: number): this;

    writeLongDateTime(value: Date | number | string, offset?: number): this;

    seek(offset?: number): this;

    head(): this;

    getBuffer(): ArrayBuffer;

    dispose(): void;

    writeInt8(value: number, offset?: number, littleEndian?: boolean): this;
    writeInt16(value: number, offset?: number, littleEndian?: boolean): this;
    writeInt32(value: number, offset?: number, littleEndian?: boolean): this;
    writeUint8(value: number, offset?: number, littleEndian?: boolean): this;
    writeUint16(value: number, offset?: number, littleEndian?: boolean): this;
    writeUint32(value: number, offset?: number, littleEndian?: boolean): this;
    writeFloat32(value: number, offset?: number, littleEndian?: boolean): this;
    writeFloat64(value: number, offset?: number, littleEndian?: boolean): this;
  }

  class OTFReader {
    private font: TTF.TTFObject;

    private options: {
        subset: number[];
    };

    constructor(options?: { subset?: number[] });

    protected readBuffer(buffer: ArrayBuffer): TTF.TTFObject;

    protected resolveGlyf(ttf: TTF.TTFObject): void;

    protected cleanTables(font: TTF.TTFObject): void;

    read(buffer: ArrayBuffer): TTF.TTFObject;

    dispose(): void;
  }

  class Font {
    static create(): Font;

    static create(buffer: FontInput, options: FontReadOptions): Font;

    static toBase64(buffer: FontInput): string;

    data: TTF.TTFObject;

    readEmpty(): Font;

    read(buffer: FontInput, options: FontReadOptions): Font;

    write(options: { toBuffer: true } & FontWriteOptions): Buffer;

    write<T extends FontType>(options: {type: T} & FontWriteOptions): T extends 'svg' ? string : FontOutput;

    toBase64(options: FontWriteOptions, buffer?: FontInput): string;

    set(data: TTF.TTFObject): Font;

    get(): TTF.TTFObject;

    optimize(outRef?: OptimizeResult): Font;

    compound2simple(): Font;

    sort(): Font;

    find(condition: FindCondition): TTF.Glyph[];

    merge(font: Font, options: MergeOptions): Font;

    getHelper(): TTFHelper;
  }

  interface Woff2 {
    isInited: () => boolean;

    init(wasmUrl?: string | ArrayBuffer): Promise<Woff2>;

    encode(ttfBuffer: ArrayBuffer | Buffer | UInt8[]): Uint8Array;

    decode(woff2Buffer: ArrayBuffer | Buffer | UInt8[]): Uint8Array;
  }

  interface IconObject {
    fontFamily: string;
    iconPrefix: string;
    glyfList: Array<{
      code: string;
      codeName: string;
      name: string;
      id: string;
    }>;
  }

  interface Core {
    Font: typeof Font;

    createFont(buffer: FontInput, options: FontReadOptions): Font;

    createFont(): Font;

    woff2: Woff2;
    TTF: typeof TTFHelper;
    TTFReader: typeof TTFReader;
    TTFWriter: typeof TTFWriter;
    Reader: typeof Reader;
    Writer: typeof Writer;
    OTFReader: typeof OTFReader;
    otf2ttfobject: (arrayBuffer: ArrayBuffer, options: any) => TTF.TTFObject;
    ttf2eot: (arrayBuffer: ArrayBuffer, options?: any) => ArrayBuffer;
    eot2ttf: (arrayBuffer: ArrayBuffer, options?: any) => ArrayBuffer;
    ttf2woff: (
      arrayBuffer: ArrayBuffer,
      options?: {
        metadata: any;
        deflate?: (rawData: UInt8[]) => UInt8[];
      }
    ) => ArrayBuffer;
    woff2ttf: (
      buffer: ArrayBuffer,
      options?: {
        inflate?: (deflatedData: UInt8[]) => UInt8[];
      }
    ) => ArrayBuffer;
    ttf2svg: (
      arrayBuffer: ArrayBuffer | TTF.TTFObject,
      options?: {
        metadata: string;
      }
    ) => string;
    svg2ttfobject: (
      svg: string | Document,
      options?: { combinePath: boolean }
    ) => TTF.TTFObject;
    ttf2base64: (arrayBuffer: ArrayBuffer) => string;
    ttf2icon: (
      arrayBuffer: ArrayBuffer | TTF.TTFObject,
      options?: {
        metadata: any;
        iconPrefix?: string;
      }
    ) => IconObject;
    ttftowoff2: (arrayBuffer: ArrayBuffer, options?: any) => Uint8Array;
    woff2tottf: (arrayBuffer: ArrayBuffer, options?: any) => Uint8Array;
    toArrayBuffer: (buffer: Buffer | UInt8[]) => ArrayBuffer;
    toBuffer: (buffer: ArrayBuffer | UInt8[]) => Buffer;
  }

  const core: Core;
}

export const Font: typeof FontEditor.Font;
export const woff2: FontEditor.Woff2;
export const createFont: FontEditor.Core["createFont"];

declare const fonteditorCore: FontEditor.Core;
export default fonteditorCore;
