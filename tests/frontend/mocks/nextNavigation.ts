/** Next.js navigation 测试替身，具体行为由各测试文件 vi.mock 覆盖。 */

export function useRouter() {
  return {
    push: () => undefined,
    replace: () => undefined,
    back: () => undefined,
  };
}

export function useParams() {
  return {};
}

export function useSearchParams() {
  return new URLSearchParams();
}
