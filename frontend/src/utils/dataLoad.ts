export const readJson = async (file: File, validator?: (data: any) => void) => {
  return new Promise<any[]>((resolve, reject) => {
    const reader = new FileReader();

    reader.onload = function (e: any) {
      const content = e.target.result;
      const records = JSON.parse(content);

      if (validator) {
        for (const record of records) {
          try {
            validator(record);
          } catch (e) {
            reject(e);
          }
        }
      }

      resolve(records);
    };

    reader.onerror = function (e) {
      reject(e);
    };

    reader.readAsText(file);
  });
};
