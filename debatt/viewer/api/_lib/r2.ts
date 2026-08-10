// Cloudflare R2 access via aws4fetch (S3-compatible SigV4). Two buckets:
// private (raw uploads) and public (published index.json, timeline.json and
// hosted video, served via PUBLIC_MEDIA_BASE_URL).

import { AwsClient } from "aws4fetch";
import { requireEnv } from "./env";

export interface R2 {
  presignPut(bucket: string, key: string, expiresSec: number): Promise<string>;
  head(bucket: string, key: string): Promise<boolean>;
  getJson<T>(bucket: string, key: string): Promise<T | null>;
  putJson(bucket: string, key: string, value: unknown, cacheControl: string): Promise<void>;
  copy(srcBucket: string, srcKey: string, dstBucket: string, dstKey: string): Promise<void>;
}

function objectUrl(endpoint: string, bucket: string, key: string): string {
  return `${endpoint}/${bucket}/${encodeURI(key)}`;
}

export function r2Client(): R2 {
  const accountId = requireEnv("R2_ACCOUNT_ID");
  const endpoint = `https://${accountId}.r2.cloudflarestorage.com`;
  const aws = new AwsClient({
    accessKeyId: requireEnv("R2_ACCESS_KEY_ID"),
    secretAccessKey: requireEnv("R2_SECRET_ACCESS_KEY"),
    service: "s3",
    region: "auto",
  });

  return {
    async presignPut(bucket, key, expiresSec) {
      const url = new URL(objectUrl(endpoint, bucket, key));
      url.searchParams.set("X-Amz-Expires", String(expiresSec));
      const signed = await aws.sign(new Request(url, { method: "PUT" }), {
        aws: { signQuery: true },
      });
      return signed.url;
    },

    async head(bucket, key) {
      const res = await aws.fetch(objectUrl(endpoint, bucket, key), { method: "HEAD" });
      return res.ok;
    },

    async getJson(bucket, key) {
      const res = await aws.fetch(objectUrl(endpoint, bucket, key));
      if (res.status === 404) return null;
      if (!res.ok) throw new Error(`R2 GET ${key}: ${res.status}`);
      return (await res.json()) as never;
    },

    async putJson(bucket, key, value, cacheControl) {
      const res = await aws.fetch(objectUrl(endpoint, bucket, key), {
        method: "PUT",
        headers: { "content-type": "application/json", "cache-control": cacheControl },
        body: JSON.stringify(value),
      });
      if (!res.ok) throw new Error(`R2 PUT ${key}: ${res.status}`);
    },

    async copy(srcBucket, srcKey, dstBucket, dstKey) {
      const res = await aws.fetch(objectUrl(endpoint, dstBucket, dstKey), {
        method: "PUT",
        headers: { "x-amz-copy-source": `/${srcBucket}/${encodeURI(srcKey)}` },
      });
      if (!res.ok) throw new Error(`R2 COPY ${srcKey} -> ${dstKey}: ${res.status}`);
    },
  };
}

export function videoKey(debateId: string): string {
  return `debatt/${debateId}/video.mp4`;
}

export function timelineKey(debateId: string): string {
  return `debatt/${debateId}/timeline.json`;
}

export const INDEX_KEY = "index.json";
